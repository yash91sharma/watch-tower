# Test app for the WT Docker tests and E2E tests. See app.sh.
FROM busybox:1.37.0
COPY app.sh /app.sh
# Healthy while /tmp/ok exists. retries=1, so that a test sees the change fast.
HEALTHCHECK --interval=2s --timeout=2s --start-period=1s --retries=1 CMD ["test", "-f", "/tmp/ok"]
ENTRYPOINT ["sh", "/app.sh"]
