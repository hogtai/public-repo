terraform {
  backend "remote" {
    organization = "thoglund"
    workspaces {
      name = "terraform-2T-thoglund"
    }
  }
}
