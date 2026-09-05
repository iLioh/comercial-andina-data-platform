#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="iLioh/comercial-andina-data-platform"
ENVIRONMENT="dev"
RESOURCE_GROUP="rg-comercial-andina-dev"
LOCATION="chilecentral"
IDENTITY_NAME="id-github-comercial-andina-dev"
SHARED_RESOURCE_GROUP="rg-banco-andino-cicd"
ACR_NAME="acrbancoandino84621"
LOG_WORKSPACE="workspace-rgbancoandinocicd37iy"

if ! az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" \
  --output none 2>/dev/null; then
  az identity create --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" --output none
fi

CLIENT_ID=$(az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" \
  --query clientId --output tsv)
PRINCIPAL_ID=$(az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" \
  --query principalId --output tsv)
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
TENANT_ID=$(az account show --query tenantId --output tsv)
DEPLOYER_PRINCIPAL_ID=$(az ad signed-in-user show --query id --output tsv)

if ! az identity federated-credential show --name github-environment-dev \
  --identity-name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" \
  --output none 2>/dev/null; then
  az identity federated-credential create --name github-environment-dev \
    --identity-name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" \
    --issuer "https://token.actions.githubusercontent.com" \
    --subject "repo:${REPOSITORY}:environment:${ENVIRONMENT}" \
    --audiences "api://AzureADTokenExchange" --output none
fi

RG_SCOPE=$(az group show --name "$RESOURCE_GROUP" --query id --output tsv)
ACR_SCOPE=$(az acr show --name "$ACR_NAME" --resource-group "$SHARED_RESOURCE_GROUP" \
  --query id --output tsv)
LOG_SCOPE=$(az monitor log-analytics workspace show --workspace-name "$LOG_WORKSPACE" \
  --resource-group "$SHARED_RESOURCE_GROUP" --query id --output tsv)

assign_role() {
  local role="$1"
  local scope="$2"
  local existing
  existing=$(az role assignment list --assignee "$PRINCIPAL_ID" --scope "$scope" \
    --query "[?roleDefinitionName=='$role'].id | [0]" --output tsv)
  if [[ -z "$existing" ]]; then
    az role assignment create --assignee-object-id "$PRINCIPAL_ID" \
      --assignee-principal-type ServicePrincipal --role "$role" --scope "$scope" \
      --output none
  fi
}

assign_role Contributor "$RG_SCOPE"
assign_role "Role Based Access Control Administrator" "$RG_SCOPE"
assign_role AcrPush "$ACR_SCOPE"
assign_role "Role Based Access Control Administrator" "$ACR_SCOPE"
assign_role "Log Analytics Contributor" "$LOG_SCOPE"

printf 'AZURE_CLIENT_ID=%s\n' "$CLIENT_ID"
printf 'AZURE_TENANT_ID=%s\n' "$TENANT_ID"
printf 'AZURE_SUBSCRIPTION_ID=%s\n' "$SUBSCRIPTION_ID"
printf 'DEPLOYER_PRINCIPAL_ID=%s\n' "$DEPLOYER_PRINCIPAL_ID"
