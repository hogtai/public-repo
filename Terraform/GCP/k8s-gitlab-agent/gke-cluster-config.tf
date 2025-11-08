resource "google_container_cluster" "primary" {
  name                     = var.cluster_name
  location                 = var.gcp_region
  remove_default_node_pool = true
  initial_node_count       = 1
  min_master_version       = "1.27.3-gke.100"
  description              = var.cluster_description
  network                  = google_compute_network.int_poc_vpc.self_link
  subnetwork               = google_compute_subnetwork.int_poc_subnet.self_link
  deletion_protection      = false

  resource_usage_export_config {
    enable_network_egress_metering       = true
    enable_resource_consumption_metering = true
    bigquery_destination {
      dataset_id = "interactive_prod_cluster_usage"
    }
  }

  ip_allocation_policy {
    services_secondary_range_name = "services"
    cluster_secondary_range_name  = "pods"
  }

  private_cluster_config {
    enable_private_endpoint = "false"
    enable_private_nodes    = "true"
    master_ipv4_cidr_block  = "10.250.128.0/28"
  }
  # Setting an empty username and password explicitly disables basic auth
  master_auth {
    client_certificate_config {
      issue_client_certificate = true
    }
  }

  maintenance_policy {
    daily_maintenance_window {
      start_time = "01:00"
    }
  }

  vertical_pod_autoscaling {
    enabled = false
  }

  lifecycle {
    ignore_changes = [node_pool, min_master_version]
  }
}

resource "google_container_node_pool" "primary_nodes" {
  name     = "${var.cluster_name}-node-pool"
  location = var.gcp_region
  cluster  = google_container_cluster.primary.name

  initial_node_count = var.node_count
  version            = "1.27.3-gke.100"

  lifecycle {
    ignore_changes = [
      version,
      initial_node_count
    ]
  }

  management {
    auto_repair  = "true"
    auto_upgrade = "true"
  }

  autoscaling {
    min_node_count = "1"
    max_node_count = "2"
  }

  node_config {
    preemptible  = false
    machine_type = var.machine_type

    metadata = {
      disable-legacy-endpoints = "true"
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
      "https://www.googleapis.com/auth/servicecontrol",
      "https://www.googleapis.com/auth/service.management",
      "https://www.googleapis.com/auth/compute",
      "https://www.googleapis.com/auth/devstorage.read_only",
      "https://www.googleapis.com/auth/cloud-platform",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
      "https://www.googleapis.com/auth/pubsub",
      "https://www.googleapis.com/auth/datastore",
      "https://www.googleapis.com/auth/trace.append",
      "https://www.googleapis.com/auth/sqlservice.admin",
      "https://www.googleapis.com/auth/bigquery",
    ]
  }
}