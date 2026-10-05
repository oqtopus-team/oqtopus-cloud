import argparse
import os

from slack_sdk import WebClient

parser = argparse.ArgumentParser()
parser.add_argument("--success", type=int)
parser.add_argument("--timestamp", type=str)
parser.add_argument("--run-url", type=str)
parser.add_argument("--deploy-target", type=str)
parser.add_argument("--message", type=str, default="")
parser.add_argument("--env", type=str, default="")
args = parser.parse_args()

slack_token = os.environ.get("SLACK_API_TOKEN")
client = WebClient(token=slack_token)

if args.success:
    if args.env == "":
        text = f'✅ Deploy successful -> "{args.deploy_target}"'
    else:
        text = f'✅ [{args.env}] Deploy successful -> "{args.deploy_target}"'

    if args.message == "":
        message = "Deployed successfully!"
    else:
        message = f"{args.message}"
        message = message[:2000]

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
                        "text": f"[{args.timestamp}] {message}",
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
    if args.env == "":
        text = f'❌ Deploy failed -> "{args.deploy_target}"'
    else:
        text = f'❌ [{args.env}] Deploy failed -> "{args.deploy_target}"'

    if args.message == "":
        message = "Deploy failed!"
    else:
        message = f"{args.message}"
        message = message[:2000]

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
                        "text": f"[{args.timestamp}] {message}",
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
