{
  let supported = {};
  const images = {
      webp: "UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAAwA0JaQAA3AA/vuUAAA=",
      avif: "AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAADybWV0YQAAAAAAAAAoaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGxpYmF2aWYAAAAADnBpdG0AAAAAAAEAAAAeaWxvYwAAAABEAAABAAEAAAABAAABGgAAAB0AAAAoaWluZgAAAAAAAQAAABppbmZlAgAAAAABAABhdjAxQ29sb3IAAAAAamlwcnAAAABLaXBjbwAAABRpc3BlAAAAAAAAAAIAAAACAAAAEHBpeGkAAAAAAwgICAAAAAxhdjFDgQ0MAAAAABNjb2xybmNseAACAAIAAYAAAAAXaXBtYQAAAAAAAAABAAEEAQKDBAAAACVtZGF0EgAKCBgANogQEAwgMg8f8D///8WfhwB8+ErK42A=",
      jxl: "/woAEBAUFwIIAAEAJABLGIsVwknk+AM=",
    },
    update = () => {
      const formats = Object.keys(images),
        name = (keep) => formats.filter(keep).join("-") || "none",
        current = name((fmt) => supported[fmt]);
      for (let mask = 0; mask < 1 << formats.length; mask++) {
        const id = name((fmt, i) => mask & (1 << i)),
          el = document.getElementById(`lf1-support-${id}`);
        if (el) el.style.display = id === current ? "inline" : "none";
      }
    },
    test = (fmt, base64) => {
      const image = new Image();
      image.onload = image.onerror = () => {
        supported[fmt] = image.width >= 1;
        update();
      };
      image.src = `data:image/${fmt};base64,${base64}`;
    };
  for (const fmt in images) test(fmt, images[fmt]);
}
