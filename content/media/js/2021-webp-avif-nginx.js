{
  let supported = {};
  const webp = 'UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAAwA0JaQAA3AA/vuUAAA=',
        avif = 'AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAAEcbWV0YQAAAAAAAABIaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGNhdmlmIC0gaHR0cHM6Ly9naXRodWIuY29tL2xpbmstdS9jYXZpZgAAAAAeaWxvYwAAAAAEQAABAAEAAAAAAUQAAQAAABcAAAAqaWluZgEAAAAAAAABAAAAGmluZmUCAAAAAAEAAGF2MDFJbWFnZQAAAAAOcGl0bQAAAAAAAQAAAHJpcHJwAAAAUmlwY28AAAAQcGFzcAAAAAEAAAABAAAAFGlzcGUAAAAAAAAAAQAAAAEAAAAQcGl4aQAAAAADCAgIAAAAFmF2MUOBAAwACggYAAYICGgIIAAAABhpcG1hAAAAAAAAAAEAAQUBAoMDhAAAAB9tZGF0CggYAAYICGgIIBoFHiAAAEQiBACwDoA=',
        update = () => {
          const ids = {
            webp: supported.webp && !supported.avif,
            avif: supported.avif && !supported.webp,
            both: supported.webp && supported.avif,
            none: !supported.webp && !supported.avif
          };
          for (const id in ids) {
            const el = document.getElementById(`lf1-support-${id}`);
            if (el) el.style.display = ids[id]?"inline":"none";
          }
        },
        test = (fmt, base64) => {
          const image = new Image();
          image.onload = image.onerror = () => {
            supported[fmt] = image.width == 1;
            update();
          }
          image.src = `data:image/${fmt};base64,${base64}`;
        };
  test('webp', webp);
  test('avif', avif);
}
