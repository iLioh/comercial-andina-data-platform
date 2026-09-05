targetScope = 'resourceGroup'

@description('Deployment environment.')
@allowed(['dev', 'qa', 'prod'])
param environment string = 'dev'

@description('Azure region selected by the university subscription policy.')
param location string = resourceGroup().location

@description('Object ID of the deployment user for temporary PoC administration.')
param deployerPrincipalId string

@description('Public client IP allowed to administer databases during the PoC.')
param clientIpAddress string

@secure()
param postgresAdminPassword string

@secure()
param sqlAdminPassword string

param postgresAdminUser string = 'caadmin'
param sqlAdminUser string = 'caadmin'

var suffix = substring(uniqueString(subscription().id, resourceGroup().id), 0, 10)
var commonTags = {
  Project: 'comercial-andina'
  Environment: environment
  ManagedBy: 'Bicep'
  DataClassification: 'Synthetic'
}
var storageName = 'stca${environment}${suffix}'
var vaultName = 'kv-ca-${environment}-${suffix}'
var postgresName = 'psql-ca-${environment}-${suffix}'
var sqlServerName = 'sql-ca-${environment}-${suffix}'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: commonTags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    isHnsEnabled: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 7 }
    containerDeleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

resource raw 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'raw'
  properties: { publicAccess: 'None' }
}
resource manifests 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'manifests'
  properties: { publicAccess: 'None' }
}
resource quarantine 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'quarantine'
  properties: { publicAccess: 'None' }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  tags: commonTags
  properties: {
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: false
    publicNetworkAccess: 'Enabled'
    sku: { family: 'A', name: 'standard' }
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: postgresName
  location: location
  tags: commonTags
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    version: '16'
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    network: { publicNetworkAccess: 'Enabled' }
    storage: { storageSizeGB: 32, autoGrow: 'Enabled', tier: 'P4' }
    highAvailability: { mode: 'Disabled' }
  }
}

resource postgresDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: postgres
  name: 'comercial_andina'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

resource postgresAzureRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}
resource postgresClientRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: postgres
  name: 'AllowDeploymentClient'
  properties: { startIpAddress: clientIpAddress, endIpAddress: clientIpAddress }
}

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: sqlServerName
  location: location
  tags: commonTags
  properties: {
    administratorLogin: sqlAdminUser
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    restrictOutboundNetworkAccess: 'Disabled'
  }
}

resource sqlDb 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: 'comercial_andina_dw'
  location: location
  tags: commonTags
  sku: { name: 'GP_S_Gen5', tier: 'GeneralPurpose', family: 'Gen5', capacity: 1 }
  properties: {
    autoPauseDelay: 60
    minCapacity: json('0.5')
    zoneRedundant: false
    readScale: 'Disabled'
    requestedBackupStorageRedundancy: 'Local'
  }
}

resource sqlAzureRule 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sqlServer
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}
resource sqlClientRule 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sqlServer
  name: 'AllowDeploymentClient'
  properties: { startIpAddress: clientIpAddress, endIpAddress: clientIpAddress }
}

resource postgresSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'postgres-credentials'
  properties: {
    value: string({ username: postgresAdminUser, password: postgresAdminPassword, port: 5432 })
  }
  dependsOn: [postgresDb]
}
resource sqlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'sql-credentials'
  properties: {
    value: string({ username: sqlAdminUser, password: sqlAdminPassword, port: 1433 })
  }
  dependsOn: [sqlDb]
}

var keyVaultSecretsOfficer = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
var storageBlobContributor = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')

resource deployerVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: keyVault
  name: guid(keyVault.id, deployerPrincipalId, keyVaultSecretsOfficer)
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: keyVaultSecretsOfficer
  }
}
resource deployerStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, deployerPrincipalId, storageBlobContributor)
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: storageBlobContributor
  }
}

output storageAccountName string = storage.name
output keyVaultUrl string = keyVault.properties.vaultUri
output postgresHost string = postgres.properties.fullyQualifiedDomainName
output postgresDatabase string = postgresDb.name
output sqlServerHost string = '${sqlServer.name}${az.environment().suffixes.sqlServerHostname}'
output sqlDatabase string = sqlDb.name
