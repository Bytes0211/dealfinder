locals {
  availability_zones = data.aws_availability_zones.available.names
  azs_count          = min(length(local.availability_zones), 3)
}

data "aws_availability_zones" "available" {
  state = "available"
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-vpc"
      Persistent = "true" # VPC is persistent
    }
  )
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-igw"
      Persistent = "true"
    }
  )
}

# Public Subnets
resource "aws_subnet" "public" {
  count                   = local.azs_count
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = local.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-public-${local.availability_zones[count.index]}"
      Tier       = "public"
      Persistent = "true"
    }
  )
}

# Private Subnets
resource "aws_subnet" "private" {
  count             = local.azs_count
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + local.azs_count)
  availability_zone = local.availability_zones[count.index]

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-private-${local.availability_zones[count.index]}"
      Tier       = "private"
      Persistent = "true"
    }
  )
}

# Elastic IPs for NAT Gateways
resource "aws_eip" "nat" {
  count  = var.enable_nat_gateway ? local.azs_count : 0
  domain = "vpc"

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-nat-eip-${count.index + 1}"
      Persistent = "false" # NAT Gateway is destroyable
    }
  )

  depends_on = [aws_internet_gateway.main]
}

# NAT Gateways
resource "aws_nat_gateway" "main" {
  count         = var.enable_nat_gateway ? local.azs_count : 0
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-nat-${local.availability_zones[count.index]}"
      Persistent = "false" # Destroyable for cost savings
    }
  )

  depends_on = [aws_internet_gateway.main]
}

# Public Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-public-rt"
      Persistent = "true"
    }
  )
}

# Public Route
resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

# Public Route Table Association
resource "aws_route_table_association" "public" {
  count          = local.azs_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private Route Tables
resource "aws_route_table" "private" {
  count  = local.azs_count
  vpc_id = aws_vpc.main.id

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-private-rt-${local.availability_zones[count.index]}"
      Persistent = "true"
    }
  )
}

# Private Routes (only if NAT Gateway enabled)
resource "aws_route" "private_nat" {
  count                  = var.enable_nat_gateway ? local.azs_count : 0
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main[count.index].id
}

# Private Route Table Associations
resource "aws_route_table_association" "private" {
  count          = local.azs_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# VPC Endpoints for AWS Services (cost optimization)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat([aws_route_table.public.id], aws_route_table.private[*].id)

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-s3-endpoint"
      Persistent = "true"
    }
  )
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat([aws_route_table.public.id], aws_route_table.private[*].id)

  tags = merge(
    var.tags,
    {
      Name       = "${var.project_name}-${var.environment}-dynamodb-endpoint"
      Persistent = "true"
    }
  )
}
