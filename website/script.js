
document.addEventListener("DOMContentLoaded", async () => {
    // ==========================================
    // IT NEWS INTELLIGENCE DASHBOARD
    // Live News Data Integration
    // ==========================================

    const newsContainer = document.getElementById("news-container");

    if (!newsContainer) {
        console.error("News container was not found.");
        return;
    }

    // Show loading message
    newsContainer.innerHTML = "";
    const loadingMessage = document.createElement("p");
    loadingMessage.textContent = "Loading latest technology news...";
    newsContainer.appendChild(loadingMessage);

    try {
        // ==========================================
        // STEP 1: FETCH LIVE NEWS DATA
        // ==========================================

        const response = await fetch(
            `./latest-news.json?t=${Date.now()}`,
            {
                method: "GET",
                cache: "no-store"
            }
        );

        if (!response.ok) {
            throw new Error(
                `Failed to fetch news. HTTP ${response.status}`
            );
        }

        const data = await response.json();

        // ==========================================
        // STEP 2: VALIDATE NEWS DATA
        // ==========================================

        if (!Array.isArray(data.articles)) {
            throw new Error("Invalid news data format.");
        }

        newsContainer.innerHTML = "";

        if (data.articles.length === 0) {
            const emptyMessage = document.createElement("p");
            emptyMessage.textContent =
                "No technology news articles available today.";

            newsContainer.appendChild(emptyMessage);
            return;
        }

        // ==========================================
        // STEP 3: DISPLAY REPORT DATE
        // ==========================================

        if (data.date) {
            const dateLabel = document.createElement("p");
            dateLabel.className = "news-date";
            dateLabel.textContent = `Latest News Report: ${data.date}`;
            newsContainer.appendChild(dateLabel);
        }

        // ==========================================
        // STEP 4: CREATE LIVE NEWS CARDS
        // ==========================================

        data.articles.forEach((story, index) => {
            const card = document.createElement("article");
            card.className = "news-card";

            // News title
            const title = document.createElement("h3");

            const link = document.createElement("a");
            link.textContent = story.title || "Untitled Article";

            // Validate external article link
            try {
                const articleURL = new URL(story.url);

                if (
                    articleURL.protocol === "https:" ||
                    articleURL.protocol === "http:"
                ) {
                    link.href = articleURL.href;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                }
            } catch (error) {
                console.warn(
                    "Invalid article URL:",
                    story.url
                );
            }

            title.appendChild(link);

            // News source
            const source = document.createElement("p");
            source.className = "news-source";
            source.textContent =
                `Source: ${story.source || "Unknown"}`;

            // Article summary
            const summary = document.createElement("p");
            summary.className = "news-summary";
            summary.textContent =
                story.summary || "No summary available.";

            // Published date
            const published = document.createElement("p");
            published.className = "news-published";

            if (story.published) {
                const publishedDate = new Date(story.published);

                if (!Number.isNaN(publishedDate.getTime())) {
                    published.textContent =
                        `Published: ${publishedDate.toLocaleString(
                            "en-CA",
                            {
                                timeZone: "America/Toronto",
                                dateStyle: "medium",
                                timeStyle: "short"
                            }
                        )}`;
                }
            }

            // Article ranking
            const ranking = document.createElement("p");
            ranking.className = "news-ranking";
            ranking.textContent = `Top Story #${index + 1}`;

            // Add all elements to card
            card.appendChild(ranking);
            card.appendChild(title);
            card.appendChild(source);
            card.appendChild(summary);

            if (published.textContent) {
                card.appendChild(published);
            }

            // Add card to dashboard
            newsContainer.appendChild(card);
        });

        // ==========================================
        // STEP 5: SUCCESS MESSAGE IN CONSOLE
        // ==========================================

        console.log(
            `Successfully loaded ${data.articles.length} live news articles.`
        );

        console.log(
            `News report date: ${data.date || "Unknown"}`
        );

    } catch (error) {
        // ==========================================
        // STEP 6: HANDLE ERRORS
        // ==========================================

        console.error(
            "IT News Dashboard Error:",
            error
        );

        newsContainer.innerHTML = "";

        const errorMessage = document.createElement("p");
        errorMessage.textContent =
            "Unable to load the latest technology news. Please try again later.";

        newsContainer.appendChild(errorMessage);
    }
});
