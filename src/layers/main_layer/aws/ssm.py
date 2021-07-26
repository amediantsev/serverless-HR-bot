import boto3


ssm_client = boto3.client("ssm")


def get_parameter(parameter_name, decrypted=False):
    return ssm_client.get_parameter(Name=parameter_name, WithDecryption=decrypted)["Parameter"]["Value"]
