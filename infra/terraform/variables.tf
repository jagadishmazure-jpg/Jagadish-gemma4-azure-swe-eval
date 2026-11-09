variable "env" {
  description = "Environment name (dev or prod)."
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be dev or prod."
  }
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus2"
}

variable "prefix" {
  description = "Short lowercase name prefix (3-10 letters or digits)."
  type        = string
  default     = "sweeval"
  validation {
    condition     = can(regex("^[a-z0-9]{3,10}$", var.prefix))
    error_message = "prefix must be 3-10 lowercase letters or digits."
  }
}

variable "log_retention_days" {
  description = "Log Analytics retention."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags on every resource."
  type        = map(string)
  default = {
    workload = "swe-agent-eval"
    owner    = "ops-platform"
    data     = "synthetic"
  }
}

variable "vm_size" {
  description = "Cluster VM size (one NVIDIA T4 by default; enough for Gemma 4 E2B or E4B in 4-bit)."
  type        = string
  default     = "Standard_NC4as_T4_v3"
}

variable "max_nodes" {
  description = "Most nodes the cluster may scale to (it idles at 0)."
  type        = number
  default     = 1
  validation {
    condition     = var.max_nodes >= 1 && var.max_nodes <= 2
    error_message = "max_nodes must be 1 or 2."
  }
}
