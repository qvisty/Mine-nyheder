/**
 * Mine Nyheder - Frontend Application
 * Handles interest selection, feed rendering, filtering, and personalization.
 */

(function () {
    "use strict";

    // State
    let allArticles = [];
    let categories = [];
    let userInterests = [];
    let savedArticles = {};
    let activeFilter = "all";

    // DOM elements
    const onboardingModal = document.getElementById("onboardingModal");
    const settingsModal = document.getElementById("settingsModal");
    const onboardingInterests = document.getElementById("onboardingInterests");
    const settingsInterests = document.getElementById("settingsInterests");
    const onboardingDone = document.getElementById("onboardingDone");
    const saveSettings = document.getElementById("saveSettings");
    const settingsBtn = document.getElementById("settingsBtn");
    const closeSettings = document.getElementById("closeSettings");
    const categoryFilters = document.getElementById("categoryFilters");
    const articleGrid = document.getElementById("articleGrid");
    const loading = document.getElementById("loading");
    const noResults = document.getElementById("noResults");
    const articleCount = document.getElementById("articleCount");
    const lastUpdated = document.getElementById("lastUpdated");
    const refreshBtn = document.getElementById("refreshBtn");

    // --- LocalStorage ---
    function loadInterests() {
        try {
            const stored = localStorage.getItem("mineNyheder_interests");
            return stored ? JSON.parse(stored) : [];
        } catch {
            return [];
        }
    }

    function saveInterests(interests) {
        localStorage.setItem("mineNyheder_interests", JSON.stringify(interests));
    }

    function hasCompletedOnboarding() {
        return localStorage.getItem("mineNyheder_onboarded") === "true";
    }

    function markOnboarded() {
        localStorage.setItem("mineNyheder_onboarded", "true");
    }

    // --- Saved Articles ---
    function loadSavedArticles() {
        try {
            var stored = localStorage.getItem("mineNyheder_saved");
            return stored ? JSON.parse(stored) : {};
        } catch {
            return {};
        }
    }

    function persistSavedArticles() {
        localStorage.setItem("mineNyheder_saved", JSON.stringify(savedArticles));
    }

    function toggleSaved(article) {
        if (savedArticles[article.id]) {
            delete savedArticles[article.id];
        } else {
            savedArticles[article.id] = article;
        }
        persistSavedArticles();
        renderArticles();
    }

    function isSaved(articleId) {
        return !!savedArticles[articleId];
    }

    // --- API ---
    async function fetchCategories() {
        const resp = await fetch("/api/categories");
        const data = await resp.json();
        return data.categories;
    }

    async function fetchArticles() {
        const resp = await fetch("/api/articles");
        const data = await resp.json();
        return data;
    }

    async function refreshFeed() {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Opdaterer...";
        try {
            await fetch("/api/refresh", { method: "POST" });
            await loadFeed();
        } finally {
            refreshBtn.disabled = false;
            refreshBtn.textContent = "Opdater";
        }
    }

    // --- Rendering: Interest Cards ---
    function renderInterestGrid(container, selectedInterests, onChange) {
        container.innerHTML = "";
        categories.forEach(function (cat) {
            const card = document.createElement("div");
            card.className = "interest-card" + (selectedInterests.includes(cat.id) ? " selected" : "");
            card.innerHTML =
                '<span class="icon">' + cat.icon + "</span>" +
                '<span class="name">' + cat.name + "</span>";
            card.addEventListener("click", function () {
                const idx = selectedInterests.indexOf(cat.id);
                if (idx === -1) {
                    selectedInterests.push(cat.id);
                    card.classList.add("selected");
                } else {
                    selectedInterests.splice(idx, 1);
                    card.classList.remove("selected");
                }
                onChange(selectedInterests);
            });
            container.appendChild(card);
        });
    }

    // --- Rendering: Category Filters ---
    function renderCategoryFilters() {
        categoryFilters.innerHTML = "";

        const allChip = document.createElement("button");
        allChip.className = "category-chip" + (activeFilter === "all" ? " active" : "");
        allChip.textContent = "Alle";
        allChip.dataset.category = "all";
        allChip.addEventListener("click", function () {
            activeFilter = "all";
            renderCategoryFilters();
            renderArticles();
        });
        categoryFilters.appendChild(allChip);

        // "Gemte" filter chip
        var savedCount = Object.keys(savedArticles).length;
        if (savedCount > 0) {
            var savedChip = document.createElement("button");
            savedChip.className = "category-chip" + (activeFilter === "saved" ? " active" : "");
            savedChip.textContent = "Gemte (" + savedCount + ")";
            savedChip.addEventListener("click", function () {
                activeFilter = "saved";
                renderCategoryFilters();
                renderArticles();
            });
            categoryFilters.appendChild(savedChip);
        }

        // Only show categories the user is interested in (or all if none selected)
        const relevantCategories = userInterests.length > 0
            ? categories.filter(function (c) { return userInterests.includes(c.id); })
            : categories;

        relevantCategories.forEach(function (cat) {
            const chip = document.createElement("button");
            chip.className = "category-chip" + (activeFilter === cat.id ? " active" : "");
            chip.textContent = cat.icon + " " + cat.name;
            chip.dataset.category = cat.id;
            chip.addEventListener("click", function () {
                activeFilter = cat.id;
                renderCategoryFilters();
                renderArticles();
            });
            categoryFilters.appendChild(chip);
        });
    }

    // --- Rendering: Articles ---
    function getFilteredArticles() {
        // Show saved articles (including permanently saved ones not in feed)
        if (activeFilter === "saved") {
            return Object.values(savedArticles).sort(function (a, b) {
                return (b.timestamp || 0) - (a.timestamp || 0);
            });
        }

        let articles = allArticles;

        // Personalize: prioritize articles matching user interests
        if (userInterests.length > 0) {
            var matched = [];
            var unmatched = [];
            articles.forEach(function (a) {
                if (userInterests.includes(a.category)) {
                    matched.push(a);
                } else {
                    unmatched.push(a);
                }
            });
            articles = matched.concat(unmatched);
        }

        // Apply category filter
        if (activeFilter !== "all") {
            articles = articles.filter(function (a) { return a.category === activeFilter; });
        }

        return articles;
    }

    function formatTimeAgo(pubDate) {
        if (!pubDate) return "";
        try {
            var date = new Date(pubDate);
            if (isNaN(date.getTime())) return pubDate;
            var now = new Date();
            var diffMs = now - date;
            var diffMins = Math.floor(diffMs / 60000);
            if (diffMins < 1) return "Lige nu";
            if (diffMins < 60) return diffMins + " min siden";
            var diffHours = Math.floor(diffMins / 60);
            if (diffHours < 24) return diffHours + (diffHours === 1 ? " time siden" : " timer siden");
            var diffDays = Math.floor(diffHours / 24);
            if (diffDays < 7) return diffDays + (diffDays === 1 ? " dag siden" : " dage siden");
            return date.toLocaleDateString("da-DK", { day: "numeric", month: "short" });
        } catch {
            return pubDate;
        }
    }

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function getCategoryName(categoryId) {
        var cat = categories.find(function (c) { return c.id === categoryId; });
        return cat ? cat.name : categoryId;
    }

    function renderArticles() {
        var filtered = getFilteredArticles();

        articleGrid.innerHTML = "";
        noResults.classList.toggle("hidden", filtered.length > 0);

        // Update count
        var totalInteresting = userInterests.length > 0
            ? allArticles.filter(function (a) { return userInterests.includes(a.category); }).length
            : allArticles.length;

        if (activeFilter !== "all") {
            articleCount.textContent = filtered.length + " artikler i " + getCategoryName(activeFilter);
        } else if (userInterests.length > 0) {
            articleCount.textContent = totalInteresting + " relevante af " + allArticles.length + " artikler";
        } else {
            articleCount.textContent = allArticles.length + " artikler";
        }

        filtered.forEach(function (article) {
            var card = document.createElement("article");
            card.className = "article-card";
            var saved = isSaved(article.id);

            var imageHtml = "";
            if (article.imageUrl) {
                imageHtml = '<img class="article-image" src="' + escapeHtml(article.imageUrl) +
                    '" alt="" loading="lazy" onerror="this.style.display=\'none\'">';
            }

            card.innerHTML =
                imageHtml +
                '<div class="article-body">' +
                    '<div class="article-meta">' +
                        '<span class="article-category">' + escapeHtml(getCategoryName(article.category)) + "</span>" +
                        '<span class="article-source">' + escapeHtml(article.source) + "</span>" +
                        '<span class="article-time">' + escapeHtml(formatTimeAgo(article.pubDate)) + "</span>" +
                    "</div>" +
                    '<h2 class="article-title">' + escapeHtml(article.title) + "</h2>" +
                    '<p class="article-description">' + escapeHtml(article.description) + "</p>" +
                    '<div class="article-actions">' +
                        '<a class="article-link" href="' + escapeHtml(article.link) +
                            '" target="_blank" rel="noopener noreferrer">Laes mere</a>' +
                        '<button class="save-btn' + (saved ? " saved" : "") + '" aria-label="Gem artikel">' +
                            '<svg width="18" height="18" viewBox="0 0 24 24" fill="' + (saved ? "currentColor" : "none") +
                            '" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>' +
                            '<span>' + (saved ? "Gemt" : "Gem") + '</span>' +
                        "</button>" +
                    "</div>" +
                "</div>";

            card.querySelector(".save-btn").addEventListener("click", function () {
                toggleSaved(article);
            });

            articleGrid.appendChild(card);
        });
    }

    // --- Feed Loading ---
    async function loadFeed() {
        loading.classList.remove("hidden");
        articleGrid.innerHTML = "";
        noResults.classList.add("hidden");

        try {
            var data = await fetchArticles();
            allArticles = data.articles || [];

            if (data.lastUpdated) {
                var updateDate = new Date(data.lastUpdated);
                lastUpdated.textContent = "Sidst opdateret: " + updateDate.toLocaleTimeString("da-DK", {
                    hour: "2-digit", minute: "2-digit"
                });
            }
        } catch (err) {
            console.error("Failed to load articles:", err);
            allArticles = [];
            articleGrid.innerHTML =
                '<div class="error-state">' +
                '<p>Kunne ikke hente nyheder. Tjek at serveren koerer, og proev igen.</p>' +
                '<button class="btn btn-secondary" onclick="location.reload()">Proev igen</button>' +
                '</div>';
        }

        loading.classList.add("hidden");
        renderCategoryFilters();
        renderArticles();
    }

    // --- Onboarding ---
    function showOnboarding() {
        var tempInterests = [];
        onboardingModal.classList.remove("hidden");

        renderInterestGrid(onboardingInterests, tempInterests, function (selected) {
            tempInterests = selected;
            onboardingDone.disabled = selected.length === 0;
        });

        onboardingDone.addEventListener("click", function handler() {
            onboardingDone.removeEventListener("click", handler);
            userInterests = tempInterests;
            saveInterests(userInterests);
            markOnboarded();
            onboardingModal.classList.add("hidden");
            renderCategoryFilters();
            renderArticles();
        });
    }

    // --- Settings ---
    function showSettings() {
        var tempInterests = userInterests.slice();
        settingsModal.classList.remove("hidden");

        renderInterestGrid(settingsInterests, tempInterests, function (selected) {
            tempInterests = selected;
        });

        function onSave() {
            userInterests = tempInterests;
            saveInterests(userInterests);
            settingsModal.classList.add("hidden");
            activeFilter = "all";
            renderCategoryFilters();
            renderArticles();
            saveSettings.removeEventListener("click", onSave);
        }
        saveSettings.addEventListener("click", onSave);
    }

    function hideSettings() {
        settingsModal.classList.add("hidden");
    }

    // --- Init ---
    async function init() {
        // Load categories
        try {
            categories = await fetchCategories();
        } catch {
            categories = [
                { id: "teknologi", name: "Teknologi", icon: "\uD83D\uDCBB" },
                { id: "politik", name: "Politik", icon: "\uD83C\uDFDB\uFE0F" },
                { id: "sport", name: "Sport", icon: "\u26BD" },
                { id: "\u00F8konomi", name: "\u00D8konomi", icon: "\uD83D\uDCC8" },
                { id: "underholdning", name: "Underholdning", icon: "\uD83C\uDFAC" },
                { id: "videnskab", name: "Videnskab", icon: "\uD83D\uDD2C" },
            ];
        }

        // Load user interests and saved articles
        userInterests = loadInterests();
        savedArticles = loadSavedArticles();

        // Load articles
        await loadFeed();

        // Show onboarding if first visit
        if (!hasCompletedOnboarding()) {
            showOnboarding();
        }

        // Event listeners
        settingsBtn.addEventListener("click", showSettings);
        closeSettings.addEventListener("click", hideSettings);
        refreshBtn.addEventListener("click", refreshFeed);

        // Close modals on overlay click
        settingsModal.addEventListener("click", function (e) {
            if (e.target === settingsModal) hideSettings();
        });
    }

    init();
})();
