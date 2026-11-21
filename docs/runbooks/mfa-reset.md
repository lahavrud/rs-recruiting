# Runbook: reset an admin's MFA (break-glass)

Admin accounts require TOTP (#1177). Use this runbook only when the admin has
**lost both** the authenticator and every recovery code, or after
`MFA_ENCRYPTION_KEY` was rotated (which makes every stored secret unreadable).
With one recovery code left, log in with it and regenerate codes on the profile
page instead. A **locked** code step (`mfa_locked`, after 5+ wrong codes) is not
a reason to reset: it lifts by itself within an hour at most, and it means
someone else has the password, so change the password (forgot-password) first.
After `MFA_ENCRYPTION_KEY` rotation the recovery codes stop working too (they
are hashed with a key derived from it).

## What the reset does

`scripts/reset_mfa.py` → `rs_shared.services.auth.mfa_reset.reset_user_mfa`:

- deletes the user's `user_mfa` row (secret, failure count, lock), recovery
  codes and pending challenges;
- deletes **all** their refresh tokens (every session ends);
- writes an `mfa_reset_break_glass` audit row (actor empty, `detail` = your reason);
- emails the owner that their MFA was reset.

The next login is password-only, and the admin is sent straight to
`/admin/mfa-setup` to enrol again. There is no endpoint for this on purpose.

## Run it against prod

Prod RDS is VPC-only, so run the script as a one-off ECS task derived from the
live web task definition (the same pattern as the deploy's migrate gate). The
script is baked into the api image, so it must have **deployed** first.

```bash
export AWS_PROFILE=rs-prod-admin AWS_REGION=us-east-1
EMAIL=admin@example.com
REASON="lost phone and recovery codes (ticket/ref)"

aws ecs describe-task-definition --task-definition rs-recruiting-prod-web \
  --query taskDefinition \
| jq --arg e "$EMAIL" --arg r "$REASON" '
    del(.taskDefinitionArn,.revision,.status,.requiresAttributes,.compatibilities,.registeredAt,.registeredBy)
    | .family = "rs-recruiting-prod-mfa-reset"
    | .containerDefinitions |= map(select(.name == "web")
        | del(.portMappings,.dependsOn,.healthCheck)
        | .command = ["python","scripts/reset_mfa.py","--email",$e,"--reason",$r])' \
  > /tmp/mfa-reset-td.json
TD=$(aws ecs register-task-definition --cli-input-json file:///tmp/mfa-reset-td.json \
  --query taskDefinition.taskDefinitionArn --output text)

# Reuse the web service's network config.
NET=$(aws ecs describe-services --cluster rs-recruiting-prod --services rs-recruiting-prod-web \
  --query 'services[0].networkConfiguration' --output json)
aws ecs run-task --cluster rs-recruiting-prod --task-definition "$TD" \
  --launch-type FARGATE --network-configuration "$NET" --count 1
```

Check the task's log (group `/ecs/rs-recruiting-prod-web`, stream
`web/web/<task-id>`) for `MFA reset and all sessions ended for …`, then
deregister the ad-hoc task definition:

```bash
aws ecs deregister-task-definition --task-definition "$TD"
```

Afterwards: log in, enrol again, store the new recovery codes, and confirm the
`mfa_reset_break_glass` and `mfa_enrolled` rows in the admin audit log.

## Locally

```bash
uv run python scripts/reset_mfa.py --email admin@example.com --reason "testing"
```

Tested against a scratch local database on 2026-11-21.
