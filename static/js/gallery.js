// Property gallery: clicking a thumbnail swaps the main photo.
// Without JavaScript the thumbnails are plain links to the full-size image.
document.querySelectorAll("[data-gallery]").forEach((gallery) => {
  const main = gallery.querySelector("[data-gallery-main]");
  const thumbs = gallery.querySelectorAll("[data-gallery-thumb]");

  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", (event) => {
      event.preventDefault();
      main.src = thumb.href;
      main.alt = thumb.dataset.alt || "";
      thumbs.forEach((other) => other.classList.toggle("is-active", other === thumb));
    });
  });
});
