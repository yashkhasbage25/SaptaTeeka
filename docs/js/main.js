let iframeId = "chapter-content";

function navOnClickHandler(chapterName) {
    let iframe = document.getElementById(iframeId);
    iframe.src = `./${chapterName}.html`;
}