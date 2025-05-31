# .github/workflows/check_schengen.yml

name: "Schengen Slot Watcher"

on:
  schedule:
    - cron: "*/5 * * * *"      # run every 5 minutes
  workflow_dispatch:           # allow manual trigger

jobs:
  watch_slots:
    runs-on: ubuntu-latest

    steps:
      # 1) Checkout the repository
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          persist-credentials: true   # needed for pushing last_state.json

      # 2) Set up Python and install pip dependencies
      - name: Set up Python & Install dependencies
        uses: actions/setup-python@v4
        with:
          python-version: "3.x"
      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests beautifulsoup4

      # 3) Set up Node.js (needed for Playwright)
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "18"

      # 4) Install Playwright and all required system dependencies
      - name: Install Playwright + Browsers (with deps)
        run: |
          npm install playwright
          npx playwright install --with-deps

      # 5) Render the live page (with JavaScript) into rendered.html
      - name: Render Schengen appointments HTML
        run: |
          node << 'EOF'
          const { chromium } = require('playwright');
          (async () => {
            const browser = await chromium.launch({ headless: true });
            const page = await browser.newPage();
            // Navigate to the live site using CITY_SLUG and VISA_TYPE
            await page.goto(
              `https://schengenappointments.com/in/${process.env.CITY_SLUG}/${process.env.VISA_TYPE}`,
              { timeout: 60000 }
            );
            // Wait until at least one <tr> appears inside the <tbody>
            await page.waitForSelector('tbody tr', { timeout: 60000 });
            // Grab the fully-rendered HTML and write to rendered.html
            const html = await page.content();
            const fs = require('fs');
            fs.writeFileSync('rendered.html', html, 'utf-8');
            await browser.close();
          })();
          EOF
        env:
          CITY_SLUG: "dubai"
          VISA_TYPE: "tourism"

      # 6) (Optional) Show first 40 lines of rendered.html for debugging
      - name: Debug: Show rendered HTML snippet
        if: always()
        run: |
          echo "----- BEGIN rendered.html (lines 1–40) -----"
          head -n 40 rendered.html
          echo "------ END rendered.html ------"

      # 7) Run the Python slot checker (which uses rendered.html if present)
      - name: Run Schengen slot checker
        env:
          CITY_SLUG:      "dubai"
          VISA_TYPE:      "tourism"
          TARGET_COUNTRY: "Cyprus"
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          CHAT_ID:        ${{ secrets.CHAT_ID }}
          STATE_FILE:     "last_state.json"
        run: |
          python check_schengen.py

      # 8) Only commit last_state.json if it exists and has changed
      - name: Commit updated state.json if needed
        run: |
          if [ -f last_state.json ]; then
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add last_state.json
            git diff --cached --quiet || git commit -m "Update last_state.json"
            git push origin HEAD:main
          else
            echo "No last_state.json to commit."
          fi
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
