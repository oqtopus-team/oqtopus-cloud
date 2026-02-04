import os
from time import sleep

from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent

from oqtopus_cloud.worker.pending_jobs_updater.lambda_function import lambda_handler

SCHEDULING_RATE_S: int = int(os.getenv("LOCAL_WORKER_SCHEDULING_RATE_S", 60))

# event = {
#     'account': 'local',
#     'detail': '{}',
#     'detail_type': 'Scheduled Event',
#     'get_id': '4c697b22-e45a-4ca3-8533-224042839079',
#     'raw_event': '[SENSITIVE]',
#     'region': 'ap-northeast-1',
#     'replay_name': '[Cannot be deserialized]',
#     'resources': ['arn:aws:scheduler:ap-northeast-1:local:schedule/default/update_pending_jobs'],
#     'source': 'aws.scheduler',
#     'time': '2026-01-29T09:05:40Z',
#     'version': '0'
# }

event: EventBridgeEvent = EventBridgeEvent({})
context: dict = {}

if __name__ == "__main__":
    print("--- Starting Local Scheduler ---")

    while 1:
        print("\n--- Execute Pending Jobs Updater ---")
        response = lambda_handler(event, context)
        # print(json.dumps(response, indent=2))
        sleep(SCHEDULING_RATE_S)
