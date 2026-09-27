function pickBackground() {
  const images = window.BACKGROUNDS || [];
  if (images.length === 0) {
    return;
  }
  let chosen = null;
  try {
    chosen = sessionStorage.getItem("background");
  } catch (error) {}
  if (!images.includes(chosen)) {
    chosen = images[Math.floor(Math.random() * images.length)];
    try {
      sessionStorage.setItem("background", chosen);
    } catch (error) {}
  }
  const root = document.documentElement;
  root.classList.add("bg-image");
  root.style.backgroundImage =
    "linear-gradient(rgba(22, 16, 15, 0.82), rgba(22, 16, 15, 0.82)), url('/static/backgrounds/" +
    encodeURIComponent(chosen) + "')";
  root.style.backgroundSize = "cover";
  root.style.backgroundAttachment = "fixed";
  root.style.backgroundPosition = "center";
}

pickBackground();
