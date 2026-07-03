# Database TLS CA bundle

`global-bundle.pem` is the CA trust bundle `oqtopus_cloud/common/session.py` uses to
verify TLS when connecting to the database (see `DB_SSL_CA` / `_DEFAULT_DB_SSL_CA`).

It is a **combined** bundle, and it must stay combined:

1. **Amazon RDS regional CAs** — the Amazon RDS global bundle
   (`https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem`).
   These verify direct connections to **RDS instances**.
2. **Amazon Trust Services roots** — `Amazon Root CA 1`–`4`
   (`https://www.amazontrust.com/repository/AmazonRootCA{1,2,3,4}.pem`).
   These verify connections through the **RDS Proxy**, whose TLS certificate is
   issued by Amazon Trust Services (public/ACM) and chains
   `*.proxy-*.rds.amazonaws.com` → `Amazon RSA 2048 M01` → `Amazon Root CA 1`,
   **not** the Amazon RDS private CA.

> [!WARNING]
> Do **not** replace this file with only the Amazon RDS `global-bundle.pem`.
> The application connects through the RDS Proxy, and the RDS-only bundle does
> **not** contain `Amazon Root CA 1`, so verification fails with
> `SSL: CERTIFICATE_VERIFY_FAILED ... unable to get local issuer certificate`.

## Regenerate

```bash
cd backend/oqtopus_cloud/common/certs
curl -fsSL https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o global-bundle.pem
for n in 1 2 3 4; do
  curl -fsSL "https://www.amazontrust.com/repository/AmazonRootCA${n}.pem" >> global-bundle.pem
done
```

## Verify (against a reachable proxy endpoint)

```bash
openssl s_client -connect <proxy-host>:3306 -starttls mysql \
  -CAfile global-bundle.pem </dev/null 2>&1 | grep 'Verify return code'
# expect: Verify return code: 0 (ok)
```
