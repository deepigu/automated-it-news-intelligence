
document.addEventListener("DOMContentLoaded", () => {

    // Sample news stories for testing the dashboard
    const newsStories = [
        {
            title: "Artificial Intelligence",
            category: "AI & Machine Learning",
            description: "Explore developments in artificial intelligence, automation, and machine learning."
        },
        {
            title: "Cybersecurity",
            category: "Security",
            description: "Follow cybersecurity research, emerging threats, and digital protection."
        },
        {
            title: "Cloud Computing",
            category: "Cloud Technology",
            description: "Discover cloud infrastructure, software platforms, and enterprise technology."
        },
        {
            title: "Python Development",
            category: "Software Engineering",
            description: "Learn about Python, backend development, APIs, and modern programming."
        },
        {
            title: "Technology Innovation",
            category: "Technology",
            description: "Explore new technologies, hardware, and industry innovation."
        }
    ];

    const newsContainer = document.getElementById("news-container");

    if (!newsContainer) {
        console.error("News container was not found.");
        return;
    }

    newsContainer.innerHTML = "";

    newsStories.forEach((story) => {
        const card = document.createElement("article");
        card.className = "news-card";

        const title = document.createElement("h3");
        title.textContent = story.title;

        const category = document.createElement("p");
        category.textContent = story.category;

        const description = document.createElement("p");
        description.textContent = story.description;

        card.appendChild(title);
        card.appendChild(category);
        card.appendChild(description);

        newsContainer.appendChild(card);
    });

});
