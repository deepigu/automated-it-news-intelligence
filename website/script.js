
document.addEventListener("DOMContentLoaded", async () => {
    const newsContainer = document.getElementById("news-container");

    if (!newsContainer) {
        console.error("News container was not found.");
        return;
    }

    newsContainer.innerHTML = "<p>Loading latest technology news...</p>";

    try {
        const response = await fetch(
            `./latest-news.json?t=${Date.now()}`,
            { cache: "no-store" }
        );

        if (!response.ok) {
            throw new Error(`HTTP error: ${response.status}`);
        }

        const data = await response.json();

        if (!Array.isArray(data.articles)) {
            throw new Error("Invalid news data format");
        }

        newsContainer.innerHTML = "";

        if (data.articles.length === 0) {
            newsContainer.textContent = "No news articles available today.";
            return;
        }

        data.articles.forEach((story) => {
            const card = document.createElement("article");
            card.className = "news-card";

            const title = document.createElement("h3");
            const link = document.createElement("a");

            link.textContent = story.title || "Untitled article";

            try {
                const url = new URL(story.url);
                if (["https:", "http:"].includes(url.protocol)) {
                    link.href = url.href;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                }
            } catch {
                console.warn("Invalid article URL:", story.url);
            }

            title.appendChild(link);

            const source = document.createElement("p");
            source.textContent = `Source: ${story.source || "Unknown"}`;

            const summary = document.createElement("p");
            summary.textContent = story.summary || "No summary available.";

            card.appendChild(title);
            card.appendChild(source);
            card.appendChild(summary);

            newsContainer.appendChild(card);
        });

        console.log(
            `Loaded ${data.articles.length} news articles from ${data.date}`
        );

    } catch (error) {
        console.error("Failed to load news:", error);

        newsContainer.textContent =
            "Unable to load the latest news. Please try again later.";
    }
});
