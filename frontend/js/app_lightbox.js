/**
 * app_lightbox.js — Просмотрщик изображений и галерея (Lightbox).
 * Поддерживает зум (колесо, пинч-ту-зум), панорамирование, свайпы и тач-жесты.
 */
(function () {
  'use strict';

// ==================== PHOTO VIEWER / LIGHTBOX MODAL ====================
let galleryPhotos = [];
let galleryCurrentIndex = 0;
let pvScale = 1.0;
let pvTranslateX = 0;
let pvTranslateY = 0;
let pvIsDragging = false;
let pvStartX = 0;
let pvStartY = 0;
let pvInitialPinchDist = 0;
let pvInitialScale = 1.0;

function initPhotoViewer() {
  const modal = document.getElementById("photo-viewer-modal");
  const closeBtn = document.getElementById("pv-close-btn");
  const prevBtn = document.getElementById("pv-prev-btn");
  const nextBtn = document.getElementById("pv-next-btn");
  const zoomInBtn = document.getElementById("pv-zoom-in");
  const zoomOutBtn = document.getElementById("pv-zoom-out");
  const viewport = document.getElementById("pv-viewport");

  if (!modal) return;

  closeBtn?.addEventListener("click", closePhotoGallery);

  prevBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (galleryCurrentIndex > 0) {
      showGalleryImage(galleryCurrentIndex - 1);
    }
  });

  nextBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (galleryCurrentIndex < galleryPhotos.length - 1) {
      showGalleryImage(galleryCurrentIndex + 1);
    }
  });

  zoomInBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    pvScale = Math.min(4.0, pvScale + 0.5);
    updateImageTransform();
  });

  zoomOutBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    pvScale = Math.max(1.0, pvScale - 0.5);
    if (pvScale === 1.0) {
      pvTranslateX = 0;
      pvTranslateY = 0;
    }
    updateImageTransform();
  });

  // Double tap / double click to toggle zoom
  let lastTap = 0;
  viewport?.addEventListener("click", (e) => {
    if (e.target.closest("button") || e.target.closest("a")) return;
    const now = Date.now();
    if (now - lastTap < 300) {
      if (pvScale > 1.0) {
        pvScale = 1.0;
        pvTranslateX = 0;
        pvTranslateY = 0;
      } else {
        pvScale = 2.5;
      }
      updateImageTransform();
    }
    lastTap = now;
  });

  // Mouse Drag / Pan
  viewport?.addEventListener("mousedown", (e) => {
    if (pvScale > 1.0) {
      pvIsDragging = true;
      pvStartX = e.clientX - pvTranslateX;
      pvStartY = e.clientY - pvTranslateY;
    }
  });

  window.addEventListener("mousemove", (e) => {
    if (pvIsDragging && pvScale > 1.0) {
      pvTranslateX = e.clientX - pvStartX;
      pvTranslateY = e.clientY - pvStartY;
      updateImageTransform();
    }
  });

  window.addEventListener("mouseup", () => {
    pvIsDragging = false;
  });

  // Touch Pinch-to-Zoom & Pan
  viewport?.addEventListener("touchstart", (e) => {
    if (e.touches.length === 2) {
      pvInitialPinchDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      pvInitialScale = pvScale;
    } else if (e.touches.length === 1 && pvScale > 1.0) {
      pvIsDragging = true;
      pvStartX = e.touches[0].clientX - pvTranslateX;
      pvStartY = e.touches[0].clientY - pvTranslateY;
    }
  }, { passive: false });

  viewport?.addEventListener("touchmove", (e) => {
    if (e.touches.length === 2) {
      e.preventDefault();
      const currentDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      if (pvInitialPinchDist > 0) {
        pvScale = Math.min(4.0, Math.max(1.0, pvInitialScale * (currentDist / pvInitialPinchDist)));
        updateImageTransform();
      }
    } else if (e.touches.length === 1 && pvIsDragging && pvScale > 1.0) {
      e.preventDefault();
      pvTranslateX = e.touches[0].clientX - pvStartX;
      pvTranslateY = e.touches[0].clientY - pvStartY;
      updateImageTransform();
    }
  }, { passive: false });

  viewport?.addEventListener("touchend", (e) => {
    if (e.touches.length < 2) {
      pvInitialPinchDist = 0;
    }
    if (e.touches.length === 0) {
      pvIsDragging = false;
      if (pvScale <= 1.0) {
        pvScale = 1.0;
        pvTranslateX = 0;
        pvTranslateY = 0;
        updateImageTransform();
      }
    }
  });

  // Keyboard navigation
  window.addEventListener("keydown", (e) => {
    if (modal.classList.contains("hidden")) return;
    if (e.key === "Escape") closePhotoGallery();
    if (e.key === "ArrowLeft" && galleryCurrentIndex > 0) showGalleryImage(galleryCurrentIndex - 1);
    if (e.key === "ArrowRight" && galleryCurrentIndex < galleryPhotos.length - 1) showGalleryImage(galleryCurrentIndex + 1);
  });
}

function updateImageTransform() {
  const img = document.getElementById("pv-image");
  if (img) {
    img.style.transform = `translate(${pvTranslateX}px, ${pvTranslateY}px) scale(${pvScale})`;
  }
}

function openPhotoGallery(photos, startIndex, title = "", desc = "") {
  galleryPhotos = photos;
  galleryCurrentIndex = startIndex || 0;

  const modal = document.getElementById("photo-viewer-modal");
  const titleEl = document.getElementById("pv-caption-title");
  const descEl = document.getElementById("pv-caption-desc");

  if (!modal) return;

  if (titleEl) titleEl.textContent = title;
  if (descEl) descEl.textContent = desc;

  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.remove("opacity-0");
  }, 10);

  showGalleryImage(galleryCurrentIndex);
}

function showGalleryImage(idx) {
  galleryCurrentIndex = idx;
  pvScale = 1.0;
  pvTranslateX = 0;
  pvTranslateY = 0;
  updateImageTransform();

  const photo = galleryPhotos[idx];
  const img = document.getElementById("pv-image");
  const counter = document.getElementById("pv-counter");
  const dlBtn = document.getElementById("pv-download-btn");
  const prevBtn = document.getElementById("pv-prev-btn");
  const nextBtn = document.getElementById("pv-next-btn");
  const titleEl = document.getElementById("pv-caption-title");
  const descEl = document.getElementById("pv-caption-desc");

  // Support both raw string URL or object with .url
  const url = typeof photo === "string" ? photo : (photo?.url || "");

  if (img && url) {
    img.src = url;
    if (photo && typeof photo === "object" && photo.title) {
      img.alt = photo.title;
    } else if (titleEl?.textContent) {
      img.alt = titleEl.textContent;
    }
  }

  // Update caption if individual photo object provides it
  if (photo && typeof photo === "object") {
    if (photo.title && titleEl) titleEl.textContent = photo.title;
    if (photo.desc && descEl) descEl.textContent = photo.desc;
  }

  if (counter) {
    counter.textContent = `${idx + 1} / ${galleryPhotos.length}`;
  }

  if (dlBtn && url) {
    dlBtn.href = url;
    const filename = url.split("/").pop() || `photo_${idx + 1}.webp`;
    dlBtn.setAttribute("download", filename);
  }

  if (prevBtn) {
    if (galleryPhotos.length > 1 && idx > 0) {
      prevBtn.classList.remove("hidden");
    } else {
      prevBtn.classList.add("hidden");
    }
  }

  if (nextBtn) {
    if (galleryPhotos.length > 1 && idx < galleryPhotos.length - 1) {
      nextBtn.classList.remove("hidden");
    } else {
      nextBtn.classList.add("hidden");
    }
  }
}

function closePhotoGallery() {
  const modal = document.getElementById("photo-viewer-modal");
  if (!modal) return;
  modal.classList.add("opacity-0");
  setTimeout(() => {
    modal.classList.add("hidden");
    pvScale = 1.0;
    pvTranslateX = 0;
    pvTranslateY = 0;
    updateImageTransform();
  }, 200);
}

// Ensure globally accessible
window.openPhotoGallery = openPhotoGallery;
window.closePhotoGallery = closePhotoGallery;




  // Export to window
  window.initPhotoViewer = initPhotoViewer;
  window.openPhotoGallery = openPhotoGallery;
  window.closePhotoGallery = closePhotoGallery;
  window.showGalleryImage = showGalleryImage;
})();
