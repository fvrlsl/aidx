const { request } = require("../../utils/request");
Page({
  data: { type: "info_error", contact_name: "", contact_phone: "", content: "" },
  onLoad(q) { this.id = q.id; },
  set(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },
  submit() {
    request("/feedback", "POST", { merchant_id: Number(this.id), type: this.data.type, contact_name: this.data.contact_name, contact_phone: this.data.contact_phone, content: this.data.content })
      .then((r) => wx.showToast({ title: r.ticket_no, icon: "none" }))
      .catch((e) => wx.showToast({ title: e.message, icon: "none" }));
  },
});
