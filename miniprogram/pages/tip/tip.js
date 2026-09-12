const { request } = require("../../utils/request");
Page({
  data: { url: "", text: "", merchant_name_raw: "" },
  onLoad(q) { this.id = q.id; },
  set(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },
  submit() {
    request("/tips", "POST", { merchant_id: this.id ? Number(this.id) : null, ...this.data })
      .then(() => wx.showToast({ title: "已提交" }))
      .catch((e) => wx.showToast({ title: e.message, icon: "none" }));
  },
});
