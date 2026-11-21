terraform {
  required_version = ">= 1.6, < 2.0"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
  }
}
provider "azurerm" {
  subscription_id = var.subscription_id
  features {}
}
variable "subscription_id" { type = string }
variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "account_name" { type = string }
variable "private_endpoint_subnet_id" { type = string }
variable "private_dns_zone_id" { type = string }
variable "caller_object_id" { type = string }
resource "azurerm_resource_group" "example" {
  name     = var.resource_group_name
  location = var.location
  tags     = { environment = "nonproduction", purpose = "document-learning-project" }
}
resource "azurerm_cognitive_account" "example" {
  name                          = var.account_name
  resource_group_name           = azurerm_resource_group.example.name
  location                      = azurerm_resource_group.example.location
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = var.account_name
  public_network_access_enabled = false
  local_auth_enabled            = false
  tags                          = azurerm_resource_group.example.tags
}
resource "azurerm_private_endpoint" "example" {
  name                = "${var.account_name}-private"
  resource_group_name = azurerm_resource_group.example.name
  location            = azurerm_resource_group.example.location
  subnet_id           = var.private_endpoint_subnet_id
  private_service_connection {
    name                           = "account"
    private_connection_resource_id = azurerm_cognitive_account.example.id
    subresource_names              = ["account"]
    is_manual_connection           = false
  }
  private_dns_zone_group {
    name                 = "account"
    private_dns_zone_ids = [var.private_dns_zone_id]
  }
}
resource "azurerm_role_assignment" "caller" {
  scope                = azurerm_cognitive_account.example.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = var.caller_object_id
}
output "service_endpoint" { value = azurerm_cognitive_account.example.endpoint }
