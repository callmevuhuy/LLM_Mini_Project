import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDownUp, BadgeCheck, ChevronDown, ChevronLeft, ChevronRight, Filter,
  Headphones, Heart, MessageCircle, Search, ShoppingCart, Sparkles, Truck, X,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";
const money = (value) => new Intl.NumberFormat("vi-VN").format(value) + "₫";

let activeRole = "customer";

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      "X-User-Role": activeRole,
      ...options.headers,
    },
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail)
      ? body.detail.map((issue) => issue.msg).join(" ")
      : body.detail;
    throw new Error(detail || "Yêu cầu chưa thực hiện được.");
  }
  return body;
}

function App() {
  const [products, setProducts] = useState([]);
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [category, setCategory] = useState("Tất cả sản phẩm");
  const [sort, setSort] = useState("Gợi ý");
  const [priceDraft, setPriceDraft] = useState({ min: "", max: "" });
  const [priceFilter, setPriceFilter] = useState({ min: null, max: null });
  const [inStockOnly, setInStockOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sessionError, setSessionError] = useState("");
  const [cart, setCart] = useState({ items: [], subtotal: 0 });
  const [sessionReady, setSessionReady] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);
  const [checkoutData, setCheckoutData] = useState({ recipient_name: "", phone_number: "", delivery_address: "" });
  const [checkoutError, setCheckoutError] = useState("");
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [lastOrder, setLastOrder] = useState(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatDraft, setChatDraft] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [selectedSku, setSelectedSku] = useState("");
  const [selectedQuantity, setSelectedQuantity] = useState(1);
  const [cartNotice, setCartNotice] = useState("");
  const [demoRole, setDemoRoleState] = useState("customer");
  const [ragVersion, setRagVersion] = useState("1.0");
  const [reindexNotice, setReindexNotice] = useState("");
  const didInitialize = useRef(false);

  const switchRole = (newRole) => {
    activeRole = newRole;
    setDemoRoleState(newRole);
  };

  const doReindex = async (ver) => {
    try {
      setReindexNotice(`Đang re-index v${ver}...`);
      const res = await api(`/rag/reindex?version=${ver}`, { method: "POST" });
      setRagVersion(res.active_version);
      setReindexNotice(`Đã kích hoạt RAG v${res.active_version}!`);
      setTimeout(() => setReindexNotice(""), 4000);
    } catch (err) {
      setReindexNotice(`Lỗi: ${err.message}`);
      setTimeout(() => setReindexNotice(""), 4000);
    }
  };

  useEffect(() => {
    if (didInitialize.current) return;
    didInitialize.current = true;
    api("/session", { method: "POST" })
      .then(() => api("/cart"))
      .then((data) => setCart(data))
      .then(() => api("/rag/status"))
      .then((status) => {
        if (status && status.active_version) setRagVersion(status.active_version);
      })
      .then(() => setSessionReady(true))
      .catch((err) => setSessionError(`Không khởi tạo được phiên mua sắm: ${err.message}`));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const params = new URLSearchParams();
    if (submittedQuery) params.set("q", submittedQuery);
    if (category !== "Tất cả sản phẩm") params.set("category", category);
    fetch(`${API_BASE}/products?${params}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Không tải được danh sách sản phẩm.");
        return response.json();
      })
      .then((data) => { setProducts(data); setError(""); })
      .catch((err) => {
        if (err.name !== "AbortError") setError("Chưa kết nối được cửa hàng. Hãy kiểm tra backend FastAPI rồi thử tải lại.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [submittedQuery, category]);

  const categories = ["Tất cả sản phẩm", "Thời trang", "Nhà cửa", "Thực phẩm"];
  const sortedProducts = useMemo(() => {
    const items = products.filter((product) => {
      const minPrice = Math.min(...product.variants.map((variant) => variant.unit_price));
      return (priceFilter.min === null || minPrice >= priceFilter.min)
        && (priceFilter.max === null || minPrice <= priceFilter.max)
        && (!inStockOnly || product.variants.some((variant) => variant.available_quantity > 0));
    });
    if (sort === "Giá thấp đến cao") items.sort((a, b) => Math.min(...a.variants.map((v) => v.unit_price)) - Math.min(...b.variants.map((v) => v.unit_price)));
    if (sort === "Bán chạy") items.reverse();
    return items;
  }, [products, sort, priceFilter, inStockOnly]);

  function search(event) {
    event.preventDefault();
    setSubmittedQuery(query.trim());
  }

  async function openProduct(productId) {
    setDetailLoading(true);
    setDetailError("");
    setCartNotice("");
    setSelectedProduct(null);
    try {
      const product = await api(`/products/${productId}`);
      setSelectedProduct(product);
      setSelectedSku(product.variants.find((variant) => variant.available_quantity > 0)?.sku || product.variants[0]?.sku || "");
      setSelectedQuantity(1);
    } catch {
      setDetailError("Không tải được thông tin chi tiết. Vui lòng thử lại.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function addToCart() {
    if (!selectedSku || !sessionReady) return;
    try {
      const updatedCart = await api("/cart/items", {
        method: "POST",
        body: JSON.stringify({ sku: selectedSku, quantity: selectedQuantity }),
      });
      setCart(updatedCart);
      setDetailError("");
      setCartNotice("Đã thêm sản phẩm vào giỏ hàng.");
    } catch (err) {
      setDetailError(err.message);
    }
  }

  async function updateCartQuantity(sku, quantity) {
    try {
      let updated;
      if (quantity <= 0) {
        await api(`/cart/items/${encodeURIComponent(sku)}`, { method: "DELETE" });
        updated = await api("/cart");
      } else {
        updated = await api(`/cart/items/${encodeURIComponent(sku)}`, { method: "PATCH", body: JSON.stringify({ sku, quantity }) });
      }
      setCart(updated);
      setCheckoutError("");
    } catch (err) {
      setCheckoutError(err.message);
    }
  }

  async function submitCheckout(event) {
    event.preventDefault();
    if (isCheckingOut) return;
    setCheckoutError("");
    setIsCheckingOut(true);
    try {
      const order = await api("/orders", { method: "POST", body: JSON.stringify(checkoutData) });
      setCart({ items: [], subtotal: 0 });
      setLastOrder(order);
      setCheckoutData({ recipient_name: "", phone_number: "", delivery_address: "" });
    } catch (err) {
      setCheckoutError(err.message);
    } finally {
      setIsCheckingOut(false);
    }
  }

  async function sendChat(event) {
    event.preventDefault();
    const message = chatDraft.trim();
    if (!message || chatSending || !sessionReady) return;
    setChatDraft("");
    setChatMessages((items) => [...items, { role: "user", message }]);
    setChatSending(true);
    try {
      const result = await api("/chat/messages", { method: "POST", body: JSON.stringify({ message, client_message_id: crypto.randomUUID() }) });
      setChatMessages((items) => [...items, {
        role: "assistant",
        message: result.message,
        route: result.route,
        status: result.status,
        citations: result.citations || [],
        order_id: result.order_id
      }]);
    } catch (err) {
      setChatMessages((items) => [...items, { role: "assistant", message: `${err.message} Bạn có thể gửi lại tin nhắn.`, route: "error", citations: [] }]);
    } finally {
      setChatSending(false);
    }
  }

  return (
    <>
      <div style={{ background: "#1e293b", color: "#f8fafc", padding: "8px 18px", display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.85rem", borderBottom: "1px solid #334155" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "#38bdf8", fontWeight: 700 }}>✦ DEMO PHÂN QUYỀN RAG:</span>
          {[
            { id: "customer", label: "Khách hàng (Customer)" },
            { id: "staff", label: "Nhân viên (Staff)" },
            { id: "admin", label: "Quản trị viên (Admin)" }
          ].map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => switchRole(r.id)}
              style={{
                background: demoRole === r.id ? "#ee4d2d" : "#334155",
                color: "#fff",
                border: "none",
                borderRadius: 4,
                padding: "3px 10px",
                cursor: "pointer",
                fontWeight: demoRole === r.id ? 700 : 500,
                transition: "all 0.15s ease"
              }}
            >
              {r.label}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span>Chỉ mục RAG: <b style={{ color: "#4ade80" }}>v{ragVersion}</b> (31 chunks)</span>
          {demoRole === "admin" && (
            <>
              <button
                type="button"
                onClick={() => doReindex("1.1")}
                style={{ background: "#16a34a", color: "#fff", border: "none", borderRadius: 4, padding: "3px 8px", cursor: "pointer", fontWeight: 600 }}
              >
                Re-index v1.1
              </button>
              <button
                type="button"
                onClick={() => doReindex("1.0")}
                style={{ background: "#dc2626", color: "#fff", border: "none", borderRadius: 4, padding: "3px 8px", cursor: "pointer", fontWeight: 600 }}
              >
                Rollback v1.0
              </button>
            </>
          )}
          {reindexNotice && <span style={{ color: "#facc15", fontWeight: 600 }}>{reindexNotice}</span>}
        </div>
      </div>
      <div className="top-strip">
        <div className="top-inner">
          <div className="top-links"><a href="#about">Kênh Người Bán</a><i /> <a href="#download">Tải ứng dụng</a><i /> <a href="#social">Kết nối với chúng tôi</a></div>
          <div className="top-links"><a href="#notice">Thông báo</a><a href="#help"><Headphones size={14} /> Hỗ trợ</a><a href="#language">Tiếng Việt <ChevronDown size={13} /></a></div>
        </div>
      </div>
      <header className="shop-header">
        <div className="header-main">
          <a className="brand" href="#home" aria-label="Group 7 trang chủ">
            <span className="brand-mark"><ShoppingCart size={28} strokeWidth={2.2} /></span>
            <span><strong>Group 7</strong><small>mua vui mỗi ngày</small></span>
          </a>
          <form className="search-box" onSubmit={search}>
            <input aria-label="Tìm kiếm sản phẩm" placeholder="Tìm sản phẩm, danh mục và thương hiệu..." value={query} onChange={(e) => setQuery(e.target.value)} />
            <button aria-label="Tìm kiếm"><Search size={21} /></button>
          </form>
          <button className="cart-button" aria-label="Mở giỏ hàng" onClick={() => { setCartOpen(true); setLastOrder(null); }}><ShoppingCart size={27} /><span>Giỏ hàng</span>{cart.items.length > 0 && <b>{cart.items.reduce((sum, item) => sum + item.quantity, 0)}</b>}</button>
        </div>
        <div className="popular-searches"><span>Tìm kiếm phổ biến:</span><a href="#" onClick={() => { setQuery("áo"); setSubmittedQuery("áo"); }}>Áo thun cotton</a><a href="#" onClick={() => { setQuery("bình"); setSubmittedQuery("bình"); }}>Bình giữ nhiệt</a><a href="#" onClick={() => { setQuery("cà phê"); setSubmittedQuery("cà phê"); }}>Cà phê Đà Lạt</a></div>
      </header>

      <main className="page-shell">
        <section className="hero-banner">
          <div className="hero-copy"><span className="hero-kicker"><Sparkles size={15} /> GỢI Ý HÔM NAY</span><h1>Món hay mỗi ngày,<br />giao vui tận nhà.</h1><p>Khám phá những lựa chọn được tuyển chọn cho bạn.</p><button onClick={() => document.getElementById("catalog")?.scrollIntoView({ behavior: "smooth" })}>Khám phá ngay <ChevronRight size={17} /></button></div>
          <div className="hero-art" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="hero-bubble bubble-a">Ưu đãi<br /><b>mỗi ngày</b></div><div className="hero-bubble bubble-b"><span>✦</span> Hàng chọn lọc</div><div className="hero-sun">G7</div></div>
        </section>

        <div className="benefit-row"><div><Truck /><span><b>Giao hàng tiện lợi</b><small>Theo dõi đơn dễ dàng</small></span></div><div><BadgeCheck /><span><b>Sản phẩm chọn lọc</b><small>Thông tin minh bạch</small></span></div><div><MessageCircle /><span><b>Trợ lý mua sắm</b><small>Hỏi đáp ngay trên trang</small></span></div></div>

        <section className="catalog-section" id="catalog">
          <aside className="filters">
            <h2><Filter size={17} /> BỘ LỌC TÌM KIẾM</h2>
            <div className="filter-group"><h3>Danh mục</h3>{categories.map((item) => <button key={item} className={category === item ? "filter-option selected" : "filter-option"} onClick={() => setCategory(item)}><span className="radio-dot" />{item}</button>)}</div>
            <div className="filter-group"><h3>Tình trạng</h3><label className="check-option"><input type="checkbox" checked={inStockOnly} onChange={(e) => setInStockOnly(e.target.checked)} /> Còn hàng</label></div>
            <div className="filter-group"><h3>Khoảng giá (từ giá SKU thấp nhất)</h3><div className="price-range"><input type="number" min="0" aria-label="Giá tối thiểu" placeholder="₫ TỪ" value={priceDraft.min} onChange={(e) => setPriceDraft((current) => ({ ...current, min: e.target.value }))} /><span>—</span><input type="number" min="0" aria-label="Giá tối đa" placeholder="₫ ĐẾN" value={priceDraft.max} onChange={(e) => setPriceDraft((current) => ({ ...current, max: e.target.value }))} /></div><button className="apply-filter" onClick={() => setPriceFilter({ min: priceDraft.min ? Number(priceDraft.min) : null, max: priceDraft.max ? Number(priceDraft.max) : null })}>ÁP DỤNG</button></div>
            <div className="filter-note">Giá và tình trạng hàng được tải từ dữ liệu cửa hàng.</div>
          </aside>

          <div className="catalog-content">
            <div className="section-heading"><div><span className="eyebrow">CỬA HÀNG DEMO</span><h2>{submittedQuery ? <>Kết quả cho <em>“{submittedQuery}”</em></> : "Khám phá sản phẩm"}</h2></div><span className="result-count">{products.length} sản phẩm</span></div>
            <div className="sort-bar"><span><ArrowDownUp size={15} /> Sắp xếp theo</span>{["Gợi ý", "Mới nhất", "Bán chạy"].map((item) => <button key={item} className={sort === item ? "sort-active" : ""} onClick={() => setSort(item)}>{item}</button>)}<select value={sort === "Giá thấp đến cao" ? sort : ""} onChange={(e) => e.target.value && setSort(e.target.value)} aria-label="Sắp xếp theo giá"><option value="">Giá</option><option>Giá thấp đến cao</option></select><span className="sort-pages">1 / 1 <ChevronLeft size={16} /><ChevronRight size={16} /></span></div>

            {error ? <div className="state-card error-state"><div>Không thể tải cửa hàng</div><p>{error}</p><button onClick={() => window.location.reload()}>Thử lại</button></div> : loading ? <div className="product-grid">{Array.from({ length: 6 }, (_, i) => <div className="product-skeleton" key={i}><div /><span /><span /></div>)}</div> : sortedProducts.length ? <div className="product-grid">{sortedProducts.map((product) => <ProductCard key={product.id} product={product} onView={() => openProduct(product.id)} />)}</div> : <div className="state-card">Chưa tìm thấy sản phẩm phù hợp. Thử từ khóa khác nhé.</div>}
          </div>
        </section>

        <footer><div className="footer-mark">Group 7</div><span>Giao diện cửa hàng demo cho dự án AI Live Commerce Order Assistant.</span><span>Giá và tồn kho hiển thị từ API demo.</span></footer>
      </main>

      <button className={chatOpen ? "chat-launcher chat-open" : "chat-launcher"} onClick={() => setChatOpen((open) => !open)} aria-label={chatOpen ? "Đóng trợ lý" : "Mở trợ lý mua sắm"}>{chatOpen ? <X size={20} /> : <><MessageCircle size={21} /><span>Trợ lý mua sắm</span><b>AI</b></>}</button>
      {chatOpen && <section className="chat-preview" aria-label="Trợ lý mua sắm"><div className="chat-head"><span className="chat-avatar"><Sparkles size={17} /></span><div><b>Trợ lý mua sắm</b><small>{chatSending ? "Đang xử lý…" : "Hỗ trợ mua sắm demo"}</small></div><button onClick={() => setChatOpen(false)} aria-label="Đóng"><X size={18} /></button></div>        <div className="chat-body">
          <div className="chat-welcome">Xin chào! Mình có thể giúp bạn tìm hiểu thông số sản phẩm, chính sách đổi trả/bảo hành và đặt hàng nhanh chóng.</div>
          {chatMessages.map((item, index) => (
            <div key={index} className={`chat-message ${item.role === "user" ? "chat-message-user" : "chat-message-assistant"}`}>
              <span>{item.message}</span>
              {item.route && (
                <small style={{ display: "inline-block", marginTop: 4, padding: "2px 6px", borderRadius: 4, background: item.route === "knowledge_query" ? "#e0f2fe" : item.route === "mixed" ? "#fef3c7" : item.status === "access_denied" ? "#fee2e2" : "rgba(0,0,0,0.05)", color: item.route === "knowledge_query" ? "#0284c7" : item.route === "mixed" ? "#b45309" : item.status === "access_denied" ? "#dc2626" : "inherit", fontWeight: 600 }}>
                  {item.route === "knowledge_query" ? "📚 Hỏi đáp tài liệu (RAG)" :
                   item.route === "mixed" ? "⚡ Hỗn hợp (RAG + Đơn hàng)" :
                   item.route === "pending_confirmation" ? "✓ Đơn chờ xác nhận" :
                   item.route === "needs_information" ? "ℹ Cần thêm thông tin" :
                   item.route === "handoff" ? "👤 Hỗ trợ nhân viên" :
                   item.route === "out_of_stock" ? "⚠ Không đủ tồn kho" :
                   item.status === "access_denied" ? "🔒 Bị từ chối quyền truy cập" :
                   item.status === "insufficient_evidence" ? "🔍 Thiếu dữ liệu tài liệu" : item.route}
                </small>
              )}
              {item.citations && item.citations.length > 0 && (
                <div style={{ marginTop: 6, paddingTop: 6, borderTop: "1px dashed rgba(0,0,0,0.12)", fontSize: "0.78rem" }}>
                  <div style={{ fontWeight: 600, color: "#ea580c", display: "flex", alignItems: "center", gap: 4 }}>
                    ✦ Nguồn trích dẫn ({item.citations.length}):
                  </div>
                  {item.citations.map((c, ci) => (
                    <div key={ci} style={{ marginTop: 2, color: "#475569" }}>
                      • <b>{c.source}</b> (v{c.version}) <i>— {c.section}</i>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {chatSending && <div className="chat-typing">Trợ lý đang soạn câu trả lời…</div>}
        </div><form className="chat-composer" onSubmit={sendChat}><input value={chatDraft} onChange={(e) => setChatDraft(e.target.value)} maxLength={1500} placeholder="Hỏi giá, tồn kho hoặc đặt hàng…" disabled={!sessionReady || chatSending} /><button disabled={!sessionReady || chatSending || !chatDraft.trim()} aria-label="Gửi"><ChevronRight size={18} /></button></form></section>}
      {(detailLoading || detailError || selectedProduct) && <div className="modal-backdrop" onClick={() => { setSelectedProduct(null); setDetailError(""); setCartNotice(""); }}><section className="product-modal" role="dialog" aria-modal="true" aria-label="Chi tiết sản phẩm" onClick={(event) => event.stopPropagation()}><button className="modal-close" onClick={() => { setSelectedProduct(null); setDetailError(""); setCartNotice(""); }} aria-label="Đóng"><X size={19} /></button>{detailLoading ? <p>Đang tải chi tiết sản phẩm…</p> : detailError && !selectedProduct ? <p className="modal-error">{detailError}</p> : selectedProduct && <><img src={selectedProduct.image_url} alt={selectedProduct.name} /><div className="modal-content"><span className="product-category">{selectedProduct.category}</span><h2>{selectedProduct.name}</h2><p>{selectedProduct.description}</p><h3>Phân loại sản phẩm</h3><div className="variant-list">{selectedProduct.variants.map((variant) => <button type="button" className={selectedSku === variant.sku ? "variant-option chosen" : "variant-option"} key={variant.sku} onClick={() => { setSelectedSku(variant.sku); setSelectedQuantity(1); setCartNotice(""); }} disabled={variant.available_quantity < 1}><span><b>{Object.values(variant.attributes).join(" · ")}</b><small>SKU: {variant.sku}</small></span><strong>{money(variant.unit_price)}</strong><em>{variant.available_quantity > 0 ? `Còn ${variant.available_quantity}` : "Hết hàng"}</em></button>)}</div><div className="add-to-cart-row"><label>Số lượng <input type="number" min="1" step="1" max={selectedProduct.variants.find((variant) => variant.sku === selectedSku)?.available_quantity || 1} value={selectedQuantity} onChange={(event) => { const quantity = Math.floor(Number(event.target.value)); setSelectedQuantity(Number.isFinite(quantity) ? Math.max(1, quantity) : 1); }} /></label><button disabled={!sessionReady || !selectedSku} onClick={addToCart}>Thêm vào giỏ</button></div>{detailError && <p className="inline-error">{detailError}</p>}{cartNotice && <p className="success-inline">{cartNotice}</p>}<small className="modal-footnote">Thông tin được tải từ API catalog.</small></div></>}</section></div>}
      {cartOpen && <div className="modal-backdrop cart-backdrop" onClick={() => { setCartOpen(false); setLastOrder(null); }}><section className="cart-drawer" role="dialog" aria-modal="true" aria-label="Giỏ hàng" onClick={(event) => event.stopPropagation()}><header><div><span className="eyebrow">GROUP 7</span><h2>{lastOrder ? "Đã tạo đơn nháp" : "Giỏ hàng"}</h2></div><button className="modal-close" onClick={() => { setCartOpen(false); setLastOrder(null); }} aria-label="Đóng"><X size={19} /></button></header>{sessionError && <p className="inline-error">{sessionError}</p>}{lastOrder ? <div className="order-success"><span className="success-mark">✓</span><h3>Yêu cầu đặt hàng đã được ghi nhận</h3><p>Đơn <b>#{lastOrder.id.slice(0, 10).toUpperCase()}</b> đang chờ xác nhận. Chưa có thanh toán hoặc trừ kho.</p><div className="success-total">Tổng tiền <strong>{money(lastOrder.total_amount)}</strong></div><button onClick={() => { setCartOpen(false); setLastOrder(null); }}>Tiếp tục mua sắm</button></div> : <><div className="cart-items">{cart.items.length ? cart.items.map((item) => <div className="cart-item" key={item.sku}><div className="cart-item-main"><b>{item.product_name}</b><small>{Object.values(item.attributes).join(" · ")} · {item.sku}</small><strong>{money(item.unit_price)} <span>× {item.quantity}</span></strong>{item.quantity > item.available_quantity && <em>Kho hiện chỉ còn {item.available_quantity}</em>}</div><div className="quantity-control"><button onClick={() => updateCartQuantity(item.sku, item.quantity - 1)} aria-label="Giảm số lượng">−</button><span>{item.quantity}</span><button disabled={item.quantity >= item.available_quantity} onClick={() => updateCartQuantity(item.sku, item.quantity + 1)} aria-label="Tăng số lượng">+</button></div></div>) : <div className="empty-cart"><ShoppingCart size={30} /><p>Giỏ hàng đang trống.</p><small>Chọn một sản phẩm để bắt đầu.</small></div>}</div><form className="checkout-form" onSubmit={submitCheckout}><h3>Thông tin nhận hàng</h3><label>Người nhận<input required minLength="2" maxLength="120" value={checkoutData.recipient_name} onChange={(event) => setCheckoutData({ ...checkoutData, recipient_name: event.target.value })} placeholder="Tên người nhận demo" /></label><label>Số điện thoại<input required type="tel" minLength="8" maxLength="30" value={checkoutData.phone_number} onChange={(event) => setCheckoutData({ ...checkoutData, phone_number: event.target.value })} placeholder="0900000000 (số giả)" /></label><label>Địa chỉ giao hàng<textarea required minLength="10" maxLength="500" value={checkoutData.delivery_address} onChange={(event) => setCheckoutData({ ...checkoutData, delivery_address: event.target.value })} placeholder="Địa chỉ demo, không dùng thông tin thật" /></label>{checkoutError && <p className="inline-error">{checkoutError}</p>}<div className="cart-total"><span>Tạm tính</span><strong>{money(cart.subtotal)}</strong></div><small className="checkout-note">Đơn tạo ở trạng thái chờ xác nhận; tồn kho chưa bị trừ.</small><button className="checkout-submit" disabled={!cart.items.length || !sessionReady || isCheckingOut}>{isCheckingOut ? "Đang gửi…" : "Gửi yêu cầu đặt hàng"}</button></form></>}</section></div>}
    </>
  );
}

function ProductCard({ product, onView }) {
  const price = Math.min(...product.variants.map((variant) => variant.unit_price));
  const inStock = product.variants.some((variant) => variant.available_quantity > 0);
  const stockCount = product.variants.reduce((sum, variant) => sum + variant.available_quantity, 0);
  return <article className="product-card"><div className="product-image-wrap"><img src={product.image_url} alt={product.name} loading="lazy" /><span className="product-label">{product.category}</span><span className="favorite" aria-hidden="true"><Heart size={17} /></span></div><div className="product-info"><span className="product-category">{product.category}</span><h3>{product.name}</h3><p className="product-description">{product.description}</p><div className="price-line"><strong>{money(price)}</strong><span>/ sản phẩm từ</span></div><div className="product-meta"><span>{product.variants.length} phân loại</span><span className="stock"><i className={inStock ? "stock-dot" : "stock-dot out"} />{inStock ? `Còn ${stockCount}` : "Hết hàng"}</span></div><div className="card-bottom"><span>{product.variants.length} SKU trong catalog</span><button onClick={onView}>Xem chi tiết</button></div></div></article>;
}

export default App;
