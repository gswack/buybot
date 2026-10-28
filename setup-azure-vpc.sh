#!/bin/bash
set -e  # stop on first error

## Assuming user is already logged in via `az login` and has the right subscription selected.

# ==== Config ====
RG="rg-products"
LOCATION="eastus"
VNET="vnet-products"
SUBNET_PUBLIC="subnet-public"
SUBNET_PRIVATE="subnet-private"
NSG_PUBLIC="nsg-public"
NSG_PRIVATE="nsg-private"
VM1="vm-node1"
VM2="vm-node2"
ADMIN_USER="azureuser"
VM_SIZE="Standard_B1s"

echo "==> Creating resource group..."
az group create --name $RG --location $LOCATION

echo "==> Creating VNet + public subnet..."
az network vnet create \
  --resource-group $RG \
  --name $VNET \
  --address-prefix 10.0.0.0/16 \
  --subnet-name $SUBNET_PUBLIC \
  --subnet-prefix 10.0.1.0/24

echo "==> Creating private subnet..."
az network vnet subnet create \
  --resource-group $RG \
  --vnet-name $VNET \
  --name $SUBNET_PRIVATE \
  --address-prefix 10.0.2.0/24

echo "==> Creating NAT Gateway for private subnet..."
az network public-ip create \
  --resource-group $RG \
  --name pip-natgw \
  --sku Standard \
  --allocation-method Static

az network nat gateway create \
  --resource-group $RG \
  --name natgw-products \
  --public-ip-addresses pip-natgw \
  --idle-timeout 10

az network vnet subnet update \
  --resource-group $RG \
  --vnet-name $VNET \
  --name $SUBNET_PRIVATE \
  --nat-gateway natgw-products

echo "==> Creating Route Table for public subnet..."
az network route-table create \
  --resource-group $RG \
  --name rt-public

az network vnet subnet update \
  --resource-group $RG \
  --vnet-name $VNET \
  --name $SUBNET_PUBLIC \
  --route-table rt-public

echo "==> Creating NSGs..."
az network nsg create --resource-group $RG --name $NSG_PUBLIC
az network nsg create --resource-group $RG --name $NSG_PRIVATE

echo "==> Adding NSG rules..."
az network nsg rule create \
  --resource-group $RG --nsg-name $NSG_PUBLIC \
  --name Allow-SSH --priority 100 --protocol Tcp \
  --destination-port-ranges 22 --access Allow --direction Inbound

az network nsg rule create \
  --resource-group $RG --nsg-name $NSG_PUBLIC \
  --name Allow-NodeApp --priority 110 --protocol Tcp \
  --destination-port-ranges 3000 --access Allow --direction Inbound

az network nsg rule create \
  --resource-group $RG --nsg-name $NSG_PRIVATE \
  --name Allow-From-Public-Subnet --priority 100 --protocol Tcp \
  --destination-port-ranges 3000 --source-address-prefixes 10.0.1.0/24 \
  --access Allow --direction Inbound

echo "==> IMPORTANT: attaching NSGs at the SUBNET level (not relying on VM auto-NSG)..."
az network vnet subnet update \
  --resource-group $RG --vnet-name $VNET --name $SUBNET_PUBLIC \
  --network-security-group $NSG_PUBLIC

az network vnet subnet update \
  --resource-group $RG --vnet-name $VNET --name $SUBNET_PRIVATE \
  --network-security-group $NSG_PRIVATE

echo "==> Creating public IP for vm-node1..."
az network public-ip create \
  --resource-group $RG \
  --name pip-vm1 \
  --sku Standard \
  --allocation-method Static

echo "==> Creating vm-node1 (public subnet)..."
az vm create \
  --resource-group $RG \
  --name $VM1 \
  --vnet-name $VNET \
  --subnet $SUBNET_PUBLIC \
  --nsg "" \
  --public-ip-address pip-vm1 \
  --image Ubuntu2204 \
  --admin-username $ADMIN_USER \
  --generate-ssh-keys \
  --size $VM_SIZE

echo "==> Creating vm-node2 (private subnet, no public IP)..."
az vm create \
  --resource-group $RG \
  --name $VM2 \
  --vnet-name $VNET \
  --subnet $SUBNET_PRIVATE \
  --nsg "" \
  --public-ip-address "" \
  --image Ubuntu2204 \
  --admin-username $ADMIN_USER \
  --generate-ssh-keys \
  --size $VM_SIZE

echo "==> Done. Fetching IPs..."
az vm list-ip-addresses --resource-group $RG --output table

echo ""
echo "Next manual steps (not automated by this script):"
echo "  - SSH into $VM1, install Node.js, clone repo, npm install, run public-app"
echo "  - SSH into $VM2 (via $VM1 as jump host), install Node.js, clone repo, npm install, run private-app"
echo "  - Update PRIVATE_API IP in public-app/index.js to match $VM2's private IP"
