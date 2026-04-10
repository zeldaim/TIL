resource "docker_image" "elasticsearch" {
  name = "docker.elastic.co/elasticsearch/elasticsearch:8.12.0"
  keep_locally = true
}

resource "docker_container" "elasticsearch" {
  image = docker_image.elasticsearch.image_id
  name  = "elasticsearch-tf"
  ports {
    internal = 9200
    external = 9202
  }
  env = [
    "discovery.type=single-node",
    "xpack.security.enabled=false",
    "ES_JAVA_OPTS=-Xms512m -Xmx512m"
  ]
}

resource "docker_image" "kibana" {
  name = "docker.elastic.co/kibana/kibana:8.12.0"
  keep_locally = true
}

resource "docker_container" "kibana" {
  image = docker_image.kibana.image_id
  name  = "kibana-tf"
  ports {
    internal = 5601
    external = 5602
  }
  depends_on = [docker_container.elasticsearch]
}