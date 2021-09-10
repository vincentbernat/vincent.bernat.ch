{
  let supported = {};
  const webp = 'UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAAwA0JaQAA3AA/vuUAAA=',
        avif = 'AAAAHGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZgAAARNtZXRhAAAAAAAAACFoZGxyAAAAAAAAAABwaWN0AAAAAAAAAAAAAAAAAAAAAA5waXRtAAAAAAABAAAAImlsb2MAAAAAREAAAQABAAAAAAE3AAEAAAAAAAAAGgAAACNpaW5mAAAAAAABAAAAFWluZmUCAAAAAAEAAGF2MDEAAAAAk2lwcnAAAABzaXBjbwAAABNjb2xybmNseAACAAIABoAAAAAMYXYxQ4EADAAAAAAUaXNwZQAAAAAAAAABAAAAAQAAAChjbGFwAAAAAQAAAAEAAAABAAAAAf////EAAAAC////8QAAAAIAAAAQcGl4aQAAAAADCAgIAAAAGGlwbWEAAAAAAAAAAQABBYGCA4SFAAAAIm1kYXQSAAoFGAAGxCAyDxJQAABgAAAAAABo0hUtVg==',
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
