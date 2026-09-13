(function () {
    "use strict";

    var sections = [];
    var nextId = 0;

    document.querySelectorAll(".content > h2").forEach(function (heading) {
        if (heading.classList.contains("foldable-heading")) return;

        var nodes = [];
        var node = heading.nextSibling;
        while (node && !/^(H1|H2)$/.test(node.nodeName)) {
            nodes.push(node);
            node = node.nextSibling;
        }
        // Empty headings have nothing to fold. Preserve raw HTML/text nodes too.
        if (!nodes.some(function (item) {
            return item.nodeType === 1 || (item.nodeType === 3 && item.textContent.trim());
        })) return;

        var body = document.createElement("div");
        body.className = "foldable-section";
        do {
            body.id = "foliate-section-" + (++nextId);
        } while (document.getElementById(body.id));
        heading.after(body);
        nodes.forEach(function (item) { body.appendChild(item); });

        var label = heading.cloneNode(true);
        label.querySelectorAll(".header-anchor").forEach(function (anchor) { anchor.remove(); });
        var title = label.textContent.trim();
        var button = document.createElement("button");
        button.type = "button";
        button.className = "heading-toggle";
        button.setAttribute("aria-controls", body.id);
        var triangle = document.createElement("span");
        triangle.setAttribute("aria-hidden", "true");
        button.appendChild(triangle);

        function setExpanded(expanded) {
            body.hidden = !expanded;
            button.setAttribute("aria-expanded", String(expanded));
            button.setAttribute("aria-label", (expanded ? "Collapse" : "Expand") + " section: " + title);
        }
        setExpanded(true);
        button.addEventListener("click", function () { setExpanded(body.hidden); });
        heading.classList.add("foldable-heading");
        heading.prepend(button);
        sections.push({ heading: heading, body: body, expand: function () { setExpanded(true); } });
    });

    function revealFragment(hash) {
        if (!hash) return null;
        var id;
        try { id = decodeURIComponent(hash.slice(1)); } catch (e) { return null; }
        var target = document.getElementById(id);
        if (!target) return null;
        var revealed = false;
        sections.forEach(function (section) {
            if (section.body.hidden &&
                (section.heading.contains(target) || section.body.contains(target))) {
                section.expand();
                revealed = true;
            }
        });
        return revealed ? target : null;
    }

    // Reveal before the browser follows a TOC/permalink, including the same hash.
    document.addEventListener("click", function (event) {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey ||
            event.ctrlKey || event.shiftKey || event.altKey) return;
        var link = event.target.closest("a[href]");
        if (!link || link.hasAttribute("download") ||
            (link.target && link.target !== "_self")) return;
        var url = new URL(link.href, document.baseURI);
        if (url.origin === location.origin && url.pathname === location.pathname &&
            url.search === location.search) revealFragment(url.hash);
    });

    // Also support browser history and scripts that navigate to a fragment.
    window.addEventListener("hashchange", function () {
        var target = revealFragment(location.hash);
        if (target) target.scrollIntoView();
    });
})();
