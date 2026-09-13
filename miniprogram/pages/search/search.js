const { request } = require("../../utils/request");

Page({
  data: { q: "", items: [], suggest: false },
  onInput(e) {
    const q = e.detail.value;
    this.setData({ q });
    if (!q.trim()) return this.setData({ items: [], suggest: false });
    clearTimeout(this.t);
    this.t = setTimeout(() => {
      request(`/merchants/search?q=${encodeURIComponent(q.trim())}`, "GET").then((r) => {
        this.setData({ items: r.items, suggest: r.suggest_create });
      });
    }, 300);
  },
  go(e) {
    wx.navigateTo({ url: `/pages/merchant/merchant?id=${e.currentTarget.dataset.id}` });
  },
  create() {
    request("/merchants", "POST", { name: this.data.q.trim() }).then((r) => {
      if (r.action === "created_pending") wx.showToast({ title: "已提交待审" });
      else if (r.merchant) wx.navigateTo({ url: `/pages/merchant/merchant?id=${r.merchant.id}` });
    });
  },
});
