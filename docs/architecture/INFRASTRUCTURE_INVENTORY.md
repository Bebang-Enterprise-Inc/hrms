# Infrastructure Inventory - BEI ERP

**Last Updated:** 2026-02-26  
**Owner:** Sam Karazi  
**Next Review:** 2026-03-05  
**Evidence Basis:** AWS CLI + repo workflow/stack files audited on 2026-02-26.

## AWS Account and Region

- AWS Account ID: `051826723988`
- Caller ARN: `arn:aws:iam::051826723988:user/frappe-hrms-admin`
- Default AWS Region: `ap-southeast-1` (Asia Pacific - Singapore)

## Production Compute (Backend)

Source: `.github/workflows/build-and-deploy.yml`, `aws ec2 describe-instances`.

- Deployment target instance: `i-026b7477d27bd46d6`
- Name tag: `frappe-hrms-ec2`
- State: `running`
- Instance type: `t3.large`
- Public IP: `13.214.59.15`
- Private IP: `10.0.1.216`
- IAM instance profile: `arn:aws:iam::051826723988:instance-profile/frappe-hrms-ec2-profile`
- Docker image deployed by workflow: `samkarazi/bebang-erpnext-hrms:v15`

## Network Topology (for active backend instance)

### VPC

- VPC ID: `vpc-024bf07c5b5b74a3f`
- Name tag: `frappe-hrms-vpc`
- CIDR: `10.0.0.0/16`
- Default VPC: `false`

### Subnets

| Subnet ID | Name | CIDR | AZ | Public IP on Launch |
|---|---|---|---|---|
| `subnet-088a6ce7c4aab3934` | `frappe-hrms-public-subnet` | `10.0.1.0/24` | `ap-southeast-1a` | `true` |
| `subnet-01c2feda8231f72e5` | `frappe-hrms-private-subnet` | `10.0.2.0/24` | `ap-southeast-1b` | `false` |

### Route Tables

| Route Table | Main | Associated Subnets | Key Routes |
|---|---|---|---|
| `rtb-089e3089133af2458` (`frappe-hrms-public-rt`) | `false` | `subnet-088a6ce7c4aab3934` | `10.0.0.0/16 -> local`, `0.0.0.0/0 -> igw-0793f7f861cdbd9d6` |
| `rtb-06aff9c3a2e7d13ac` | `true` | main association | `10.0.0.0/16 -> local` |

### Internet Gateway and ACL

- Internet Gateway: `igw-0793f7f861cdbd9d6` (`frappe-hrms-igw`)
- Network ACL: `acl-0748a034ac2b84e55` (default ACL for this VPC)

### Security Group

- Security Group: `sg-0715c0db1a0eb2d8d` (`frappe-hrms-ec2-sg`)
- Ingress rules:
  - `tcp/80` from `0.0.0.0/0`
  - `tcp/443` from `0.0.0.0/0`
  - `tcp/8080` from `0.0.0.0/0`
  - `tcp/22` from `49.43.106.151/32`
- Egress rules: 1 rule (allow outbound)

## Load Balancers

Source: `aws elbv2 describe-load-balancers` filtered by `vpc-024bf07c5b5b74a3f`.

- No ELBv2 load balancers were found in the active backend VPC.

## DNS and Certificates

### DNS Resolution (live lookup)

- `hq.bebang.ph` resolves to Cloudflare addresses:
  - IPv4: `104.26.12.188`, `104.26.13.188`, `172.67.72.103`
  - IPv6: `2606:4700:20::681a:dbc`, `2606:4700:20::ac43:4867`, `2606:4700:20::681a:cbc`
- `my.bebang.ph` is `CNAME -> cname.vercel-dns.com`
  - A records observed: `76.76.21.164`, `66.33.60.34`

### Route53 and ACM

- Route53 hosted zones containing `bebang.ph`: none found (`aws route53 list-hosted-zones` filter).
- ACM certificates containing `bebang.ph`:
  - `ap-southeast-1`: none found
  - `us-east-1`: none found

## Data Stores

### Active backend stack (Docker Swarm topology in repo)

Source: `frappe_docker_build/stack-swarm.yml`.

- MariaDB service: `db` (container image `mariadb:10.6`)
- Redis services: `redis-cache`, `redis-queue`
- Persistent volumes:
  - `bebang-hrms_sites`
  - `bebang-hrms_db-data`
  - `bebang-hrms_logs`
  - `bebang-hrms_redis-queue-data`

### RDS inventory in account (separate VPC)

Source: `aws rds describe-db-instances`.

| DB Instance | Engine | Status | VPC | Public | Multi-AZ | Backup Retention |
|---|---|---|---|---|---|---|
| `bebang-cluster` | mysql | available | `vpc-047b41820662c2f02` | false | true | 7 days |
| `bebang-staging-cluster` | mysql | available | `vpc-047b41820662c2f02` | false | false | 7 days |

Note: Current BEI-ERP deployment workflow and stack file point to containerized MariaDB, not these RDS instances.

## Secrets Inventory (names only)

Source: `aws secretsmanager list-secrets` filtered for `bebang|frappe|hrms`.

- `bebang/manychatrb`

No secret values are stored in this document.

## Backup Inventory

### S3 buckets (name-level inventory)

- `bebang-bucket`
- `bebang-frappe-hrms-backups`
- `frappe-hrms-backups-67551023`

### RDS snapshots (matching `bebang` instances)

Observed manual + automated snapshots include:
- `rds:bebang-cluster-2026-02-25-16-10` (available)
- `rds:bebang-staging-cluster-2026-02-25-16-11` (available)
- Additional earlier snapshots remain available in account.

### EC2 volume snapshots for active backend instance

- Attached EBS volume: `vol-0523b11e169ca3e81` (`50 GiB`, `gp2`, `Encrypted=false`)
- Snapshots found for this volume: none (`aws ec2 describe-snapshots --filters Name=volume-id,Values=vol-0523b11e169ca3e81`)

## Gaps / Unknowns (explicit)

- Cloudflare zone/certificate/WAF configuration is not represented in AWS CLI data and needs separate Cloudflare inventory.
- This inventory records what exists; it does not yet assert which non-active resources are authoritative for production cutover.

## Update Command Set

```powershell
aws sts get-caller-identity
aws configure get region
aws ec2 describe-instances --instance-ids i-026b7477d27bd46d6
aws ec2 describe-vpcs --vpc-ids vpc-024bf07c5b5b74a3f
aws ec2 describe-subnets --filters Name=vpc-id,Values=vpc-024bf07c5b5b74a3f
aws ec2 describe-route-tables --filters Name=vpc-id,Values=vpc-024bf07c5b5b74a3f
aws ec2 describe-security-groups --group-ids sg-0715c0db1a0eb2d8d
aws elbv2 describe-load-balancers
aws route53 list-hosted-zones
aws acm list-certificates --region ap-southeast-1
aws acm list-certificates --region us-east-1
aws rds describe-db-instances
aws rds describe-db-snapshots
aws s3api list-buckets
aws secretsmanager list-secrets
```
