# Trusted Proxies

By default the rate limiter uses `REMOTE_ADDR` — the IP of the direct TCP connection — to identify clients. This is safe and requires no configuration.

If your deployment sits behind a CDN or load balancer, `REMOTE_ADDR` will always be the CDN edge IP, causing all users to share the same rate-limit bucket. Setting `TRUSTED_PROXIES` lets the app unwrap the real client IP from `X-Forwarded-For`, but only when the request genuinely arrived from one of the listed addresses.

**Why this is safe:** The app only reads `X-Forwarded-For` when `REMOTE_ADDR` itself matches a trusted CIDR. A spoofed `X-Forwarded-For` header from an untrusted source is ignored entirely.

## Configuration

Add to `settings.env`:

```
TRUSTED_PROXIES=<cidr1>,<cidr2>,...
```

The app parses these once at startup. Invalid entries are logged and skipped.

---

## Cloudflare

Cloudflare injects the real visitor IP into `X-Forwarded-For` before appending the edge node. Their published ranges are stable and small.

Current IPv4 ranges: https://www.cloudflare.com/ips-v4  
Current IPv6 ranges: https://www.cloudflare.com/ips-v6

```
TRUSTED_PROXIES=173.245.48.0/20,103.21.244.0/22,103.22.200.0/22,103.31.4.0/22,141.101.64.0/18,108.162.192.0/18,190.93.240.0/20,188.114.96.0/20,197.234.240.0/22,198.41.128.0/17,162.158.0.0/15,104.16.0.0/13,104.24.0.0/14,172.64.0.0/13,131.0.72.0/22,2400:cb00::/32,2606:4700::/32,2803:f800::/32,2405:b500::/32,2405:8100::/32,2a06:98c0::/29,2c0f:f248::/32
```

---

## AWS CloudFront

CloudFront publishes its edge ranges as a JSON file that is updated frequently. Use only the ranges labelled `CLOUDFRONT` in the service field.

Current ranges: https://ip-ranges.amazonaws.com/ip-ranges.json

Because the list is large and changes often, the recommended approach is a small script that fetches the JSON and regenerates `TRUSTED_PROXIES` in `settings.env` on a schedule (e.g. weekly cron).

```bash
curl -s https://ip-ranges.amazonaws.com/ip-ranges.json \
  | jq -r '[.prefixes[] | select(.service=="CLOUDFRONT") | .ip_prefix] + 
            [.ipv6_prefixes[] | select(.service=="CLOUDFRONT") | .ipv6_prefix]
            | join(",")' \
  | sed 's/^/TRUSTED_PROXIES=/' >> settings.env
```

---

## Fastly

Current ranges: https://api.fastly.com/public-ip-list

```bash
curl -s https://api.fastly.com/public-ip-list \
  | jq -r '(.addresses + .ipv6_addresses) | join(",")' \
  | sed 's/^/TRUSTED_PROXIES=/' >> settings.env
```

---

## Google Cloud CDN

Google publishes its ranges at a TXT DNS record and a JSON endpoint.

Current ranges: https://www.gstatic.com/ipranges/cloud.json  
(filter for `scope` values matching your region, or include all)

```bash
curl -s https://www.gstatic.com/ipranges/cloud.json \
  | jq -r '[.prefixes[] | .ipv4Prefix // .ipv6Prefix] | join(",")' \
  | sed 's/^/TRUSTED_PROXIES=/' >> settings.env
```

---

## Internal load balancer (no CDN)

If nginx or a load balancer runs on the same private network, list only its address:

```
TRUSTED_PROXIES=10.0.1.5/32
```
