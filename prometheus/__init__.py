DEFAULT_TEMPERATURE = 0.3

deployment_name_davinci = 'text-davinci'
deployment_name_35 = 'gpt-35-turbo'
deployment_name_35_chat = 'gpt-35-turbo-chat'
deployment_name_4 = 'gpt-4'
deployment_name_ada = 'text-embedding-ada-002'

DEPLOYMENTS = [deployment_name_4, deployment_name_35, deployment_name_35_chat]
DEPLOYMENT_HELP = f"{deployment_name_35}: completion, {deployment_name_4}, {deployment_name_35_chat}: chat completion"
