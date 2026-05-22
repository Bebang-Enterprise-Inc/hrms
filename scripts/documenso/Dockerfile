# BEI Documenso — reproducible patched image
#
# Builds documenso/documenso:v2.8.1-bei-patched from upstream + the five
# patch scripts in this directory. Replaces the previous "manually sed-patch
# a running container then docker commit" workflow — which lost patches
# (b) and (c)-on-signing-email at some point in 2026 without anyone noticing.
#
# Build:
#   docker build -t documenso/documenso:v2.8.1-bei-patched -f Dockerfile .
#
# Then deploy by recreating the documenso container from the new image
# (`docker stop documenso && docker rm documenso && docker run ...
#  documenso/documenso:v2.8.1-bei-patched`).
#
# The five patches applied here:
#   (a) Field-size multipliers in the envelope-editor bundle.
#   (b) CC recipients receive the initial signing email.
#   (c) Resend message-id captured into DocumentAuditLog (both send sites).
#   (d) Session-cookie maxAge (fixes the stale-closure 30-day OAuth outage).
#   (e) Sign-All-My-Fields button (gated to sam@bebang.ph only).
#
# Each patch script is idempotent and supports --verify-only — we apply once
# and re-verify in the same RUN layer to guarantee the image is good.

FROM documenso/documenso:v2.8.1

USER root

# Install Python only for the patching step. apk add + apk del happen in the
# same RUN layer so Python is NOT present in the final image — keeps the size
# delta vs upstream small (just the patched file diffs, ~200 KB).
COPY patch_field_sizes.py \
     patch_cc_notifications.py \
     patch_resend_id_logging.py \
     patch_session_cookie_stale_closure.py \
     patch_sign_all_button.py \
     /tmp/bei-patch/

RUN set -eux; \
    apk add --no-cache python3; \
    python3 /tmp/bei-patch/patch_field_sizes.py \
        --search-root /app/apps/remix/build/client/assets; \
    python3 /tmp/bei-patch/patch_field_sizes.py \
        --search-root /app/apps/remix/build/client/assets --verify-only; \
    python3 /tmp/bei-patch/patch_cc_notifications.py \
        --search-root /app/apps/remix/build/server; \
    python3 /tmp/bei-patch/patch_cc_notifications.py \
        --search-root /app/apps/remix/build/server --verify-only; \
    python3 /tmp/bei-patch/patch_resend_id_logging.py \
        --search-root /app/apps/remix/build/server --kind completed; \
    python3 /tmp/bei-patch/patch_resend_id_logging.py \
        --search-root /app/apps/remix/build/server --kind completed --verify-only; \
    python3 /tmp/bei-patch/patch_resend_id_logging.py \
        --search-root /app/apps/remix/build/server --kind signing; \
    python3 /tmp/bei-patch/patch_resend_id_logging.py \
        --search-root /app/apps/remix/build/server --kind signing --verify-only; \
    python3 /tmp/bei-patch/patch_session_cookie_stale_closure.py \
        --search-root /; \
    python3 /tmp/bei-patch/patch_session_cookie_stale_closure.py \
        --search-root / --verify-only; \
    python3 /tmp/bei-patch/patch_sign_all_button.py \
        --search-root /app/apps/remix/build/client/assets; \
    python3 /tmp/bei-patch/patch_sign_all_button.py \
        --search-root /app/apps/remix/build/client/assets --verify-only; \
    rm -rf /tmp/bei-patch; \
    apk del python3

USER nodejs

LABEL bei.documenso.patches="field-sizes,cc-notifications,resend-id-logging,session-cookie-maxage,sign-all-button"
LABEL bei.documenso.upstream="documenso/documenso:v2.8.1"
LABEL bei.documenso.rebuild-cmd="docker build -t documenso/documenso:v2.8.1-bei-patched -f scripts/documenso/Dockerfile scripts/documenso/"
