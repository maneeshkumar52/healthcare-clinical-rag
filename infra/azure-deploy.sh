#!/bin/bash
set -e

RESOURCE_GROUP="rg-clinical-rag"
LOCATION="uksouth"
APP_NAME="healthcare-clinical-rag"

echo "Deploying Healthcare Clinical RAG to Azure Container Apps..."

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure Container Registry
az acr create \
    --resource-group $RESOURCE_GROUP \
    --name "${APP_NAME}acr" \
    --sku Basic \
    --admin-enabled true

# Build and push container image
az acr build \
    --registry "${APP_NAME}acr" \
    --image clinical-rag:latest \
    .

# Create Container Apps environment
az containerapp env create \
    --name "${APP_NAME}-env" \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION

# Deploy Container App
az containerapp create \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment "${APP_NAME}-env" \
    --image "${APP_NAME}acr.azurecr.io/clinical-rag:latest" \
    --target-port 8000 \
    --ingress external \
    --min-replicas 1 \
    --max-replicas 5 \
    --env-vars \
        AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint \
        AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
        AZURE_SEARCH_ENDPOINT=secretref:azure-search-endpoint \
        AZURE_SEARCH_API_KEY=secretref:azure-search-key \
        COSMOS_ENDPOINT=secretref:cosmos-endpoint \
        COSMOS_KEY=secretref:cosmos-key \
        JWT_SECRET=secretref:jwt-secret

echo "Deployment complete!"
echo "App URL: https://${APP_NAME}.<env-domain>.azurecontainerapps.io"
