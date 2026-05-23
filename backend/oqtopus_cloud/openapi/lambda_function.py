import pathlib


def lambda_handler(event, context):
    filepath = pathlib.Path(__file__).parent / "openapi.yaml"
    content = filepath.read_text()
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/yaml"},
        "body": content,
    }
