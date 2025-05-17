import argparse
import os

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

parser = argparse.ArgumentParser()
parser.add_argument("--success", type=bool)
parser.add_argument("--timestamp", type=str)
parser.add_argument("--run_url", type=str)
parser.add_argument("--deploy_target", type=str)
args = parser.parse_args()

slack_token = os.environ.get("SLACK_API_TOKEN")
client = WebClient(token=slack_token)

if args.success:
    text = f"✅ Deploy successful {args.deploy_target}"
    attachments = [
        {
            "color": "#00dd00",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Log*",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"[{args.timestamp}] Deployed successfully!",
                    },
                },
                {
                    "type": "divider",
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Action*",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{args.run_url}",
                    },
                },
            ],
        }
    ]

else:
    text = f"❌ Deploy failed {args.deploy_target}"
    attachments = [
        {
            "color": "#dd0000",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Log*",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"[{args.timestamp}] Deploy failed!",
                    },
                },
                {
                    "type": "divider",
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Action*",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{args.run_url}",
                    },
                },
            ],
        }
    ]

response = client.chat_postMessage(
    channel=os.environ.get("SLACK_CHANNEL_NAME"),
    text=text,
    attachments=attachments,
)
