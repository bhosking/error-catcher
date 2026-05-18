from bisect import insort
from collections import defaultdict
from datetime import datetime, timezone
from difflib import get_close_matches
import json
from math import ceil
import os
from urllib.parse import quote, quote_plus
import uuid

import boto3

ACCOUNT_ID = os.environ["ACCOUNT_ID"]
ALARM_NAME = os.environ["ALARM_NAME"]
RECENT_ERRORS_BUCKET = os.environ["RECENT_ERRORS_BUCKET"]
RECENT_ERRORS_MINUTES = int(os.environ["RECENT_ERRORS_MINUTES"])
SES_SOURCE_EMAIL = os.environ["SES_SOURCE_EMAIL"]
SES_TARGET_EMAIL = os.environ["SES_TARGET_EMAIL"]
TRIGGER_NAME = os.environ["TRIGGER_NAME"]
CLOUDWATCH_PERIOD = 60  # Seconds for CloudWatch metric period
LEADING_MILLISECONDS = 100  # Milliseconds to include before error in logs
MAX_ERROR_LENGTH = 250
MAX_SEARCH_WINDOW_MS = 24 * 60 * 60 * 1000  # Sanity check for search window
RECENT_ERRORS_FILE = "recent_errors.json"
SAME_ERROR_SIMILARITY = 0.7  # Error similarity to consider the same error
SEARCH_WINDOW_START_PADDING_MS = 30 * 1000
# The full 15 minutes because cloudwatch will backdate the errors
# to the start of the function invocation, so the actual error could happen
# up to 15 minutes later. Add an additional period buffer as metric timestamps
# round down to the start of the period.
SEARCH_WINDOW_END_PADDING_MS = (30 + 15 * 60 + CLOUDWATCH_PERIOD) * 1000
SUBJECT = f"AWS Lambda Function Error Alert for Account {ACCOUNT_ID}"


cloudwatch = boto3.client("cloudwatch")
events = boto3.client("events")
logs = boto3.client("logs")
ses = boto3.client("ses")
s3 = boto3.client("s3")


class ErrorFormat:
    def __init__(self, error_pattern, error_transform_function):
        self.pattern = error_pattern
        self.transform_function = error_transform_function

    def transform(self, error_message):
        try:
            return self.transform_function(error_message)
        except Exception as e:
            print(
                f"Bad transform of error message: {e}.\nError message: {error_message}"
            )
            return error_message


def format_error_normal(error_message):
    return error_message.split("\n")[0].split(" ", 1)[1]


def format_error_timeout(error_message):
    duration = error_message.split("Billed Duration: ")[1].split(" ms")[0]
    return f"Function timed out after {duration}ms"


def format_error_report(error_message):
    return error_message.split("Error Type: ")[1]


def format_error_requestid1(error_message):
    return error_message.split(" ", 2)[2]


def format_error_requestid2(error_message):
    return error_message.split("Error: ", 1)[1]


def format_error_botocore(error_message):
    return error_message.split(" ", 1)[1]


ERROR_FORMATS = [
    # [ERROR] ValueError: max() iterable argument is empty\nTraceback (most recent call last):\n
    ErrorFormat(
        "%^\\[ERROR\\] %",
        format_error_normal,
    ),
    # REPORT RequestId: 2ef395ad-4666-4984-b282-5ce567ea718d\tDuration: 2000.00 ms\tBilled Duration: 2000 ms\tMemory Size: 4096 MB\tMax Memory Used: 147 MB\tStatus: timeout\n
    ErrorFormat(
        "%^REPORT .+Status: timeout%",
        format_error_timeout,
    ),
    # REPORT RequestId: 68038378-e817-489b-97dc-1709db3d7631\tDuration: 8948.73 ms\tBilled Duration: 8949 ms\tMemory Size: 2048 MB\tMax Memory Used: 2048 MB\tInit Duration: 495.04 ms\tStatus: error\tError Type: Runtime.OutOfMemory\n
    ErrorFormat(
        "%^REPORT .+Status: error%",
        format_error_report,
    ),
    # 2025-07-02T06:13:12.232Z 4dfdda04-721f-4241-b1ee-4601f4c4f371 Task timed out after 60.06 second\n
    ErrorFormat(
        "%^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}Z [0-9a-f-]{36} %",
        format_error_requestid1,
    ),
    # RequestId: efcd9dee-1027-4fe6-bd1a-9da80b77a25c Error: Runtime exited with error: signal: killed Runtime.ExitError
    ErrorFormat(
        "%^RequestId: [0-9a-f-]{36}\\sError: %",
        format_error_requestid2,
    ),
    # botocore.errorfactory.MessageRejected: An error occurred (MessageRejected) when calling the SendEmail operation: Email address is not verified. The following identities failed the check in region AP-SOUTHEAST-2: admin@example.com
    ErrorFormat(
        "%^botocore\\.\\S*[eE]rror%",
        format_error_botocore,
    ),
]


class FunctionError:
    def __init__(self, function_name, new_error_metrics, recent_errors):
        self.function_name = function_name
        self.latest_metric = None
        self.earliest_metric = None
        self.log_errors = {}
        self.error_metrics_by_timestamp = self.combine_error_metrics(
            tuplify(recent_errors.get("error_metrics_by_timestamp", [])),
            new_error_metrics,
        )
        self.log_event_ids_by_timestamp = tuplify(
            recent_errors.get("log_event_ids_by_timestamp", [])
        )
        self.recent_event_ids = set(
            event_id for _, event_id in self.log_event_ids_by_timestamp
        )
        if self.latest_metric is not None:
            self.find_errors()
            self.match_metrics_to_errors()
        else:
            print(f"No fresh error metrics found for function {function_name}.")

    def combine_error_metrics(self, recent_error_metrics, new_error_metrics):
        brand_new_metrics = set(new_error_metrics) - set(recent_error_metrics)
        if brand_new_metrics:
            self.earliest_metric = min(brand_new_metrics)[0]
            self.latest_metric = max(brand_new_metrics)[0]
        return sorted((dict(recent_error_metrics) | dict(new_error_metrics)).items())

    def get_log_event_link(self, log_event):
        stream_name = quote_plus(log_event["logStreamName"])
        start = log_event["timestamp"] - LEADING_MILLISECONDS
        event_id = log_event["eventId"]
        log_stream_location = quote(
            f"{stream_name}?start={start}&refEventId={event_id}"
        ).replace("%", "$")
        log_group_link = self.get_log_group_link()
        return f"{log_group_link}/log-events/{log_stream_location}"

    def get_log_group_link(self):
        log_group = quote(quote_plus(f"/aws/lambda/{self.function_name}")).replace(
            "%", "$"
        )
        region = logs.meta.region_name
        return f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#logsV2:log-groups/log-group/{log_group}"

    def find_errors(self):
        errors = {}
        search_from = int(self.earliest_metric - SEARCH_WINDOW_START_PADDING_MS)
        search_to = int(self.latest_metric + SEARCH_WINDOW_END_PADDING_MS)
        for error_format in ERROR_FORMATS:
            kwargs = {
                "logGroupName": f"/aws/lambda/{self.function_name}",
                "filterPattern": error_format.pattern,
                "startTime": search_from,
                "endTime": search_to,
            }
            next_token = True
            while next_token:
                print(
                    f"Calling logs.filter_log_events with kwargs: {json.dumps(kwargs)}"
                )
                response = logs.filter_log_events(**kwargs)
                print(f"Received response: {json.dumps(response, default=str)}")
                for event in response.get("events", []):
                    event_id = event["eventId"]
                    if event_id in self.recent_event_ids:
                        continue
                    transformed_message = trim_error(
                        error_format.transform(event["message"])
                    )
                    insort(
                        self.log_event_ids_by_timestamp, (event["timestamp"], event_id)
                    )
                    matching_error = get_close_matches(
                        transformed_message,
                        errors.keys(),
                        n=1,
                        cutoff=SAME_ERROR_SIMILARITY,
                    )
                    if matching_error:
                        errors[matching_error[0]]["count"] += 1
                    else:
                        errors[transformed_message] = {
                            "count": 1,
                            "link": self.get_log_event_link(event),
                        }
                next_token = response.get("nextToken")
                kwargs["nextToken"] = next_token
        self.log_errors = errors

    def error_html(self, message, count, link):
        return f"""
            <tr>
                <td>{self.function_name}</td>
                <td>{message}</td>
                <td>{count}</td>
                <td><a href="{link}" target="_blank" rel="noopener noreferrer">View Logs</a></td>
            </tr>"""

    def all_errors_html(self):
        return "".join(
            self.error_html(message, details["count"], details["link"])
            for message, details in self.log_errors.items()
        )

    def add_missing_log_event(self, timestamp):
        print(
            f"Missing log error for metric with timestamp {timestamp} for function {self.function_name}, perhaps a new error pattern is present."
        )
        message = "Error not found - manual log inspection required."
        existing_error = self.log_errors.get(message)
        if existing_error:
            existing_error["count"] += 1
        else:
            print(
                f"Adding generic link to log group for function {self.function_name}."
            )
            self.log_errors[message] = {
                "count": 1,
                "link": self.get_log_group_link(),
            }
        insort(self.log_event_ids_by_timestamp, (timestamp, str(uuid.uuid4())))

    def match_metrics_to_errors(self):
        # Match error metrics to log errors, to look for missing logs
        j = len(self.log_event_ids_by_timestamp) - 1
        for timestamp, error_count in reversed(self.error_metrics_by_timestamp):
            for _ in range(error_count):
                if j < 0:
                    # Not enough log events for the error metrics
                    self.add_missing_log_event(timestamp)
                else:
                    if self.log_event_ids_by_timestamp[j][0] < timestamp:
                        # No log event for this error metric
                        self.add_missing_log_event(timestamp)
                    else:
                        j -= 1

    def get_new_recent_errors(self, from_timestamp):
        return {
            "error_metrics_by_timestamp": [
                (timestamp, count)
                for timestamp, count in self.error_metrics_by_timestamp
                if timestamp >= from_timestamp
            ],
            "log_event_ids_by_timestamp": [
                (timestamp, event_id)
                for timestamp, event_id in self.log_event_ids_by_timestamp
                if timestamp >= from_timestamp
            ],
        }


def tuplify(list_of_lists):
    return [tuple(item) for item in list_of_lists]


def send_email(subject, body_html):
    kwargs = {
        "Source": SES_SOURCE_EMAIL,
        "Destination": {
            "ToAddresses": [SES_TARGET_EMAIL],
        },
        "Message": {
            "Subject": {"Data": subject},
            "Body": {
                "Html": {"Data": body_html},
            },
        },
    }
    print(f"Calling ses_client.send_email with kwargs: {json.dumps(kwargs)}")
    response = ses.send_email(**kwargs)
    print(f"Received response: {json.dumps(response, default=str)}")


def trim_error(error_message):
    first_line = error_message.split("\n")[0]
    if len(first_line) > MAX_ERROR_LENGTH:
        return first_line[: MAX_ERROR_LENGTH - 3] + "..."
    else:
        return first_line


def create_email_body(error_info):
    body_html = f"""
    <html>
      <head>
        <style>
          body {{
            font-family: Arial, sans-serif;
            color: #333;
          }}
          .container {{
            max-width: 800px;
            margin: auto;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
            background-color: #f9f9f9;
          }}
          h1 {{
            color: #d13212;
          }}
          h2 {{
            color: #33548e;
          }}
          p {{
            line-height: 1.6;
          }}
          table {{
            border-collapse: collapse;
            width: 100%;
          }}
          th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
          }}
          th {{
            background-color: #f2f2f2;
          }}
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Lambda Function Error Alert</h1>
          <p><strong>Account ID:</strong> {ACCOUNT_ID}</p>
          <h2>Errors Detected</h2>
          <table>
            <tr>
              <th>Function Name</th>
              <th>Error Message</th>
              <th>Error Count</th>
              <th>Log Link</th>
            </tr>{error_info}
          </table>
          <p>This is an automated alert. Please do not reply to this email.</p>
        </div>
      </body>
    </html>
    """
    return body_html


def function_to_metric(function_name):
    return {
        "Id": function_name.replace("-", "_"),
        "Label": function_name,
        "MetricStat": {
            "Metric": {
                "Namespace": "AWS/Lambda",
                "MetricName": "Errors",
                "Dimensions": [
                    {
                        "Name": "FunctionName",
                        "Value": function_name,
                    },
                ],
            },
            "Period": CLOUDWATCH_PERIOD,
            "Stat": "Sum",
        },
    }


def get_all_error_html(start_ms, end_ms, track_old_errors=True):
    recent_errors = get_recent_errors() if track_old_errors else {}
    function_names = list_function_error_metrics()
    error_metrics = get_error_metrics(function_names, start_ms, end_ms)
    function_errors = []
    new_recent_errors = {}
    for function_name, function_error_metrics in error_metrics.items():
        if not function_error_metrics:
            print(f"No error metrics found for function {function_name}.")
            continue
        function_error_metrics.sort()
        function_error = FunctionError(
            function_name,
            function_error_metrics,
            recent_errors.get(function_name, {}),
        )
        function_errors.append(function_error)
        if track_old_errors:
            new_recent_errors[function_name] = function_error.get_new_recent_errors(
                start_ms
            )
    if track_old_errors:
        put_recent_errors(new_recent_errors)
    html = "".join(function.all_errors_html() for function in function_errors)
    if not html:
        print("No errors found.")
    return html


def list_function_error_metrics():
    all_functions = set()
    kwargs = {
        "Namespace": "AWS/Lambda",
        "MetricName": "Errors",
    }
    next_token = True
    while next_token:
        print(f"Calling cloudwatch.list_metrics with kwargs: {json.dumps(kwargs)}")
        response = cloudwatch.list_metrics(**kwargs)
        print(f"Received response: {json.dumps(response, default=str)}")
        all_functions.update(
            {
                dimension["Value"]
                for metric in response.get("Metrics", [])
                for dimension in metric["Dimensions"]
                if dimension["Name"] == "FunctionName"
            }
        )
        next_token = response.get("NextToken")
        kwargs["NextToken"] = next_token
    return list(all_functions)


def get_error_metrics(function_names, start_time, end_time):
    error_metrics = defaultdict(list)
    if end_time - start_time > MAX_SEARCH_WINDOW_MS:
        print("Attempting to search too large a window, aborting...")
        return error_metrics
    start_seconds = start_time // 1000 // CLOUDWATCH_PERIOD * CLOUDWATCH_PERIOD
    end_seconds = ceil(end_time / 1000 / CLOUDWATCH_PERIOD) * CLOUDWATCH_PERIOD
    kwargs = {
        "StartTime": datetime.fromtimestamp(start_seconds, tz=timezone.utc),
        "EndTime": datetime.fromtimestamp(end_seconds, tz=timezone.utc),
        "MetricDataQueries": [function_to_metric(name) for name in function_names],
    }
    next_token = True
    while next_token:
        print(
            f"Calling cloudwatch.get_metric_data with kwargs: {json.dumps(kwargs, default=str)}"
        )
        response = cloudwatch.get_metric_data(**kwargs)
        print(f"Received response: {json.dumps(response, default=str)}")
        for metric in response.get("MetricDataResults", []):
            error_timestamps = []
            for timestamp, value in zip(metric["Timestamps"], metric["Values"]):
                if value > 0:
                    error_timestamps.append(
                        (int(timestamp.timestamp() * 1000), int(value))
                    )
            if error_timestamps:
                error_metrics[metric["Label"]].extend(error_timestamps)
        next_token = response.get("NextToken")
        kwargs["NextToken"] = next_token
    return error_metrics


def get_recent_errors():
    kwargs = {
        "Bucket": RECENT_ERRORS_BUCKET,
        "Key": RECENT_ERRORS_FILE,
    }
    print(f"Calling s3.get_object with kwargs: {json.dumps(kwargs)}")
    try:
        response = s3.get_object(**kwargs)
    except s3.exceptions.NoSuchKey:
        print("No recent errors found. This is probably a good thing.")
        return {}
    print(f"Received response: {json.dumps(response, default=str)}")
    content = response["Body"].read().decode()
    return json.loads(content)


def put_recent_errors(recent_errors):
    kwargs = {
        "Bucket": RECENT_ERRORS_BUCKET,
        "Key": RECENT_ERRORS_FILE,
        "Body": json.dumps(recent_errors).encode(),
    }
    print(f"Calling s3.put_object with kwargs: {json.dumps(kwargs, default=str)}")
    response = s3.put_object(**kwargs)
    print(f"Received response: {json.dumps(response, default=str)}")


def check_schedule():
    kwargs = {"Name": TRIGGER_NAME}
    print(f"Calling events.describe_rule with kwargs: {json.dumps(kwargs)}")
    response = events.describe_rule(**kwargs)
    print(f"Received response: {json.dumps(response, default=str)}")
    return response.get("State") == "ENABLED"


def start_schedule():
    kwargs = {"Name": TRIGGER_NAME}
    print(f"Calling events.enable_rule with kwargs: {json.dumps(kwargs)}")
    response = events.enable_rule(**kwargs)
    print(f"Received response: {json.dumps(response, default=str)}")


def stop_schedule():
    kwargs = {"Name": TRIGGER_NAME}
    print(f"Calling events.disable_rule with kwargs: {json.dumps(kwargs)}")
    response = events.disable_rule(**kwargs)
    print(f"Received response: {json.dumps(response, default=str)}")


def is_alarmed():
    kwargs = {"AlarmNames": [ALARM_NAME]}
    next_token = True
    while next_token:
        print(f"Calling cloudwatch.describe_alarms with kwargs: {json.dumps(kwargs)}")
        response = cloudwatch.describe_alarms(**kwargs)
        print(f"Received response: {json.dumps(response, default=str)}")
        alarms = response.get("MetricAlarms", [])
        if alarms:
            alarm_state = alarms[0]["StateValue"]
            return alarm_state == "ALARM"
        next_token = response.get("NextToken")
        kwargs["NextToken"] = next_token
    print(f"No alarm with name {ALARM_NAME} found. Treating as always on.")
    return True


def lambda_handler(event, context):
    print("Event Received: {}".format(json.dumps(event)))
    if "start_ms" in event or "end_ms" in event:
        # If start_time and end_time are provided in the event, use them
        start_time = event.get("start_ms", 0)
        end_time = event.get(
            "end_ms", int(datetime.now(timezone.utc).timestamp() * 1000)
        )
        print(f"Running with provided window: {start_time} to {end_time}")
        error_html = get_all_error_html(start_time, end_time, track_old_errors=False)
        if error_html:
            send_email(SUBJECT, create_email_body(error_html))
    else:
        scheduled = check_schedule()
        if is_alarmed():
            if not scheduled:
                print("Alarm is active but schedule is disabled, enabling schedule.")
                start_schedule()
            end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
            start_time = end_time - RECENT_ERRORS_MINUTES * 60 * 1000
            error_html = get_all_error_html(start_time, end_time)
            if error_html:
                send_email(SUBJECT, create_email_body(error_html))
        elif scheduled:
            print("Alarm is inactive, stopping schedule.")
            stop_schedule()
