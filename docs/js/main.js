/* ==========================================================================
   सप्तशतीटीकासंग्रहः — reading-edition behaviour
   --------------------------------------------------------------------------
   Vanilla, ~100 lines, one <script> at the end of the body. This replaces
   jQuery (loaded twice), Popper and Bootstrap's JS -- roughly 250 KB of
   dependencies that existed to toggle one drawer.

   Everything here degrades: with JS off the sidebar is still visible on
   desktop, every link still works, and the text still reads.
   ========================================================================== */

(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;

  /* ---- sidebar drawer --------------------------------------------------- */

  var nav = doc.getElementById("sidebar");
  var toggle = doc.getElementById("toggleNav");
  var scrim = doc.getElementById("scrim");

  function setDrawer(open) {
    if (!nav) return;
    nav.classList.toggle("is-open", open);
    if (scrim) scrim.classList.toggle("is-open", open);
    if (toggle) toggle.setAttribute("aria-expanded", open ? "true" : "false");
    // Stop the page behind the drawer scrolling under your thumb.
    doc.body.style.overflow = open ? "hidden" : "";
  }

  if (toggle) {
    toggle.addEventListener("click", function () {
      setDrawer(!nav.classList.contains("is-open"));
    });
  }

  if (scrim) {
    scrim.addEventListener("click", function () {
      setDrawer(false);
    });
  }

  doc.addEventListener("keydown", function (e) {
    if (e.key === "Escape") setDrawer(false);
  });

  // On a phone the drawer covers the text, so following a link should shut it.
  if (nav) {
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a")) setDrawer(false);
    });
  }

  /* ---- keep the current section in view in a 23-item list --------------- */

  var scroller = doc.querySelector(".navbar__scroll");
  var active = doc.querySelector(".nav-link.active-section");
  if (scroller && active) {
    var want = active.offsetTop - scroller.clientHeight / 2 + active.offsetHeight;
    if (want > 0) scroller.scrollTop = want;
  }

  /* ---- reading theme --------------------------------------------------- */

  var MOON = "\u263D";   // ☽  offer the paper theme
  var SUN = "\u2600";    // ☀  offer the dark theme
  var themeBtn = doc.getElementById("toggleTheme");

  function paintThemeButton() {
    if (!themeBtn) return;
    var paper = root.getAttribute("data-theme") === "paper";
    themeBtn.innerHTML = paper ? SUN : MOON;
    themeBtn.setAttribute(
      "title",
      paper ? "switch to the dark reading theme"
            : "switch to the paper reading theme"
    );
  }

  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var paper = root.getAttribute("data-theme") === "paper";
      if (paper) {
        root.removeAttribute("data-theme");
      } else {
        root.setAttribute("data-theme", "paper");
      }
      try {
        localStorage.setItem("st-theme", paper ? "dark" : "paper");
      } catch (e) {
        /* private browsing: the choice just will not persist */
      }
      paintThemeButton();
    });
    paintThemeButton();
  }

  /* ---- reading progress and back-to-top -------------------------------- */

  var bar = doc.getElementById("progress");
  var totop = doc.getElementById("totop");
  var ticking = false;

  function onScroll() {
    var y = window.scrollY || doc.documentElement.scrollTop;
    var h = doc.documentElement.scrollHeight - window.innerHeight;
    if (bar) bar.style.width = (h > 0 ? (y / h) * 100 : 0) + "%";
    if (totop) totop.classList.toggle("is-on", y > 600);
    ticking = false;
  }

  window.addEventListener(
    "scroll",
    function () {
      if (!ticking) {
        ticking = true;
        window.requestAnimationFrame(onScroll);
      }
    },
    { passive: true }
  );

  onScroll();

  if (totop) {
    totop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }
})();
