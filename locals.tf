locals {
  # Define the time period for which to track recent errors
  # This should be at least 15 minutes (lambda timeout) plus 20 minutes (trigger interval)
  recent_errors_minutes = 40
}
