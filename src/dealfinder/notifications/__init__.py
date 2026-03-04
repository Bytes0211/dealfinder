"""Notification delivery clients for Deal Finder.

Provides thin wrappers around Pushover and AWS SES so the Messenger
Agent can dispatch deal alerts through either channel without coupling
dispatch logic to the underlying HTTP/boto3 details.
"""
