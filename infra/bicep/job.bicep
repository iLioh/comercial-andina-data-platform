targetScope = 'resourceGroup'

param environment string = 'dev'
param location string = resourceGroup().location
param acrName string
param acrResourceGroup string
param logAnalyticsWorkspaceName string
param logAnalyticsResourceGroup string
param imageTag string
param storageAccountName string
param keyVaultName string
param postgresHost string
param sqlServerHost string
@secure()
param prefectApiKey string
param prefectApiUrl string

var commonTags = {
  Project: 'comercial-andina'
  Environment: environment
  ManagedBy: 'Bicep'
  DataClassification: 'Synthetic'
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  scope: resourceGroup(acrResourceGroup)
  name: acrName
}
resource logs 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  scope: resourceGroup(logAnalyticsResourceGroup)
  name: logAnalyticsWorkspaceName
}
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-comercial-andina-${environment}'
  location: location
  tags: commonTags
}

var storageBlobContributor = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var keyVaultSecretsUser = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')

module acrPullAssignment 'modules/acr-pull.bicep' = {
  name: 'assign-acr-pull'
  scope: resourceGroup(acrResourceGroup)
  params: {
    acrName: acr.name
    principalId: identity.properties.principalId
  }
}
resource storageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, identity.id, storageBlobContributor)
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobContributor
  }
}
resource vaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: keyVault
  name: guid(keyVault.id, identity.id, keyVaultSecretsUser)
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUser
  }
}

var runtimeEnvironment = [
  { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
  { name: 'PREFECT_API_URL', value: prefectApiUrl }
  { name: 'PREFECT_API_KEY', secretRef: 'prefect-api-key' }
  { name: 'CA_STORAGE_ACCOUNT', value: storage.name }
  { name: 'CA_RAW_CONTAINER', value: 'raw' }
  { name: 'CA_MANIFEST_CONTAINER', value: 'manifests' }
  { name: 'CA_QUARANTINE_CONTAINER', value: 'quarantine' }
  { name: 'CA_KEY_VAULT_URL', value: keyVault.properties.vaultUri }
  { name: 'CA_POSTGRES_HOST', value: postgresHost }
  { name: 'CA_POSTGRES_DATABASE', value: 'comercial_andina' }
  { name: 'CA_POSTGRES_SECRET_NAME', value: 'postgres-credentials' }
  { name: 'CA_SQL_SERVER', value: sqlServerHost }
  { name: 'CA_SQL_DATABASE', value: 'comercial_andina_dw' }
  { name: 'CA_SQL_SECRET_NAME', value: 'sql-credentials' }
]

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-comercial-andina-${environment}'
  location: location
  tags: commonTags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: 'caj-ca-etl-${environment}'
  location: location
  tags: commonTags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 1800
      replicaRetryLimit: 2
      scheduleTriggerConfig: {
        cronExpression: '0 11 * * *'
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [{ server: acr.properties.loginServer, identity: identity.id }]
      secrets: [{ name: 'prefect-api-key', value: prefectApiKey }]
    }
    template: {
      containers: [{
        name: 'etl'
        image: '${acr.properties.loginServer}/comercial-andina/etl:${imageTag}'
        command: ['python', '-m', 'comercial_andina.flows.daily_sales']
        env: runtimeEnvironment
        resources: { cpu: json('0.5'), memory: '1Gi' }
      }]
    }
  }
  dependsOn: [acrPullAssignment, storageRole, vaultRole]
}

resource bootstrapJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'caj-ca-bootstrap-${environment}'
  location: location
  tags: commonTags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1800
      replicaRetryLimit: 1
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      registries: [{ server: acr.properties.loginServer, identity: identity.id }]
      secrets: [{ name: 'prefect-api-key', value: prefectApiKey }]
    }
    template: {
      containers: [{
        name: 'bootstrap'
        image: '${acr.properties.loginServer}/comercial-andina/etl:${imageTag}'
        command: ['comercial-andina', 'initialize']
        env: runtimeEnvironment
        resources: { cpu: json('0.5'), memory: '1Gi' }
      }]
    }
  }
  dependsOn: [acrPullAssignment, storageRole, vaultRole]
}

output jobName string = job.name
output bootstrapJobName string = bootstrapJob.name
output managedIdentityClientId string = identity.properties.clientId
