variable "project" {
  type    = string
  default = "social-pulse-510513"
}

variable "region" {
  type    = string
  default = "asia-south1"
}

variable "docai_location" {
  type    = string
  default = "us"
}

variable "github_repo" {
  description = "owner/name of the GitHub repo allowed to deploy"
  type        = string
  default     = "cgoxo/ClaimLens"
}
