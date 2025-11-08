resource "helm_release" "gitlab_agent" {
  name = "gitlab-agent"

  repository = "https://charts.gitlab.io"
  chart      = "gitlab-agent"

  create_namespace = true
  namespace        = var.agent_namespace

  set {
    name  = "config.kasAddress"
    value = var.kas_address
  }

  set {
    name  = "config.token"
    value = var.agent_token
  }

  set {
    name  = "image.tag"
    value = "v16.3.0"
  }
}