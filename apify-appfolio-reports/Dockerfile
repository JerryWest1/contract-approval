# Apify base image with Node 20 + Playwright + Chromium preinstalled.
FROM apify/actor-node-playwright-chrome:20

# Install dependencies first (better layer caching).
COPY --chown=myuser:myuser package.json ./
RUN npm install --omit=dev --no-audit --no-fund \
    && echo "Installed dependencies:" \
    && npm ls --omit=dev --all || true

# Copy the rest of the source.
COPY --chown=myuser:myuser . ./

CMD ["npm", "start", "--silent"]
