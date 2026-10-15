// Location autocomplete: asks the semantic-search API for suggestions as the visitor types.
// Without JavaScript the search box is a plain text input and the form still works.
document.querySelectorAll("[data-autocomplete]").forEach((box) => {
  const input = box.querySelector("input[type='text']");
  const list = box.querySelector("[data-autocomplete-list]");
  let items = [];
  let active = -1;
  let timer = null;
  let controller = null;

  const close = () => {
    list.hidden = true;
    list.replaceChildren();
    input.setAttribute("aria-expanded", "false");
    items = [];
    active = -1;
  };

  const highlight = (index) => {
    active = index;
    items.forEach((item, i) => item.classList.toggle("is-active", i === index));
  };

  const choose = (name) => {
    input.value = name;
    close();
    input.form.submit();
  };

  const render = (results) => {
    close();
    if (!results.length) return;
    results.forEach((result) => {
      const item = document.createElement("li");
      item.setAttribute("role", "option");
      item.className = "autocomplete__item";
      item.dataset.name = result.name;

      const name = document.createElement("span");
      name.className = "autocomplete__name";
      name.textContent = result.name;

      // tell the visitor why each suggestion is here: typed text vs similar meaning
      const tag = document.createElement("span");
      const semantic = result.match === "semantic";
      tag.className = `autocomplete__tag autocomplete__tag--${semantic ? "semantic" : "text"}`;
      tag.textContent = semantic ? "Similar" : "Name match";
      tag.title = semantic
        ? "Suggested because its name and description are close in meaning"
        : "Suggested because its name contains what you typed";

      item.append(name, tag);
      // mousedown fires before the input loses focus, so the click is not swallowed
      item.addEventListener("mousedown", (event) => {
        event.preventDefault();
        choose(result.name);
      });
      list.append(item);
    });
    items = [...list.children];
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  };

  const fetchSuggestions = async () => {
    const query = input.value.trim();
    if (query.length < 2) return close();
    if (controller) controller.abort(); // drop the answer to an older keystroke
    controller = new AbortController();
    try {
      const url = `${box.dataset.url}?q=${encodeURIComponent(query)}&limit=5`;
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) return close();
      render((await response.json()).results);
    } catch (error) {
      if (error.name !== "AbortError") close();
    }
  };

  input.setAttribute("role", "combobox");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-autocomplete", "list");
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(fetchSuggestions, 200);
  });
  input.addEventListener("keydown", (event) => {
    if (list.hidden || !items.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      highlight((active + step + items.length) % items.length);
    } else if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      choose(items[active].dataset.name);
    } else if (event.key === "Escape") {
      close();
    }
  });
  input.addEventListener("blur", close);
});
