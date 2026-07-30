/* ==========================================================================
   DocFlow Pro - Frontend Engine with Dynamic Member Authentication & OCR
   ========================================================================== */

class DocFlowApp {
  constructor() {
    this.workflows = [];
    this.activeWf = null;
    this.uploadedFilesMap = {}; // docId -> File or {front: File, back: File}
    this.transformParamsMap = {}; // slotId -> { angle, flipH, flipV, freeAngle, deblur, file }
    this.processedFilesList = []; // Array of processed file objects
    this.zipDownloadUrl = null;
    this.modalSlotId = null;
    this.modalFile = null;
    this.currentUser = null;
    this.authToken = null;

    this.init();
  }

  async init() {
    this.checkAuthStatus();
    await this.fetchWorkflows();
    this.renderServices();
  }

  // --- MEMBER AUTHENTICATION ENGINE ---
  checkAuthStatus() {
    const savedToken = localStorage.getItem("docflow_token");
    const savedUser = localStorage.getItem("docflow_username");

    if (savedToken && savedUser) {
      this.authToken = savedToken;
      this.currentUser = savedUser;
      this.showAuthenticatedApp();
    } else {
      this.showLoginModal();
    }
  }

  async handleLogin(event) {
    event.preventDefault();
    const usernameInput = document.getElementById("loginUsername").value.trim();
    const passwordInput = document.getElementById("loginPassword").value.trim();
    const errorBox = document.getElementById("loginErrorMsg");

    errorBox.style.display = "none";
    errorBox.innerText = "";

    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: usernameInput, password: passwordInput })
      });
      const data = await res.json();

      if (data.status === "success") {
        this.authToken = data.token;
        this.currentUser = data.username;

        localStorage.setItem("docflow_token", data.token);
        localStorage.setItem("docflow_username", data.username);

        this.showAuthenticatedApp();
        this.showToast(`Welcome back, Officer ${data.username}! Access Granted.`);
      } else {
        errorBox.style.display = "block";
        errorBox.innerText = data.message || "Invalid Authorized Username or Password!";
      }
    } catch (e) {
      errorBox.style.display = "block";
      errorBox.innerText = "Network or Server authentication error: " + e.message;
    }
  }

  showAuthenticatedApp() {
    document.getElementById("loginModalContainer").style.display = "none";
    document.getElementById("mainAppContent").style.display = "block";
    document.getElementById("userPillContainer").style.display = "flex";
    document.getElementById("loggedInUserLabel").innerText = `${this.currentUser} (Authorized Member)`;
  }

  showLoginModal() {
    document.getElementById("loginModalContainer").style.display = "flex";
    document.getElementById("mainAppContent").style.display = "none";
    document.getElementById("userPillContainer").style.display = "none";
  }

  logout() {
    this.authToken = null;
    this.currentUser = null;
    localStorage.removeItem("docflow_token");
    localStorage.removeItem("docflow_username");
    this.showLoginModal();
    this.showToast("Logged out safely.");
  }

  // --- ADD AUTHORIZED MEMBER ENGINE ---
  openAddMemberModal() {
    if (!this.currentUser) {
      alert("Only authorized logged-in members can add new members!");
      return;
    }
    const msgBox = document.getElementById("addMemberMsg");
    if (msgBox) {
      msgBox.style.display = "none";
      msgBox.innerText = "";
    }
    document.getElementById("addMemberModalContainer").style.display = "flex";
  }

  closeAddMemberModal() {
    document.getElementById("addMemberModalContainer").style.display = "none";
  }

  async handleAddMember(event) {
    event.preventDefault();
    const newUsername = document.getElementById("newMemberUsername").value.trim();
    const newPassword = document.getElementById("newMemberPassword").value.trim();
    const msgBox = document.getElementById("addMemberMsg");

    msgBox.style.display = "none";

    try {
      const res = await fetch("/api/add_user", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${this.authToken}`
        },
        body: JSON.stringify({ username: newUsername, password: newPassword })
      });
      const data = await res.json();

      if (data.status === "success") {
        msgBox.style.display = "block";
        msgBox.style.background = "rgba(34, 197, 94, 0.15)";
        msgBox.style.color = "var(--accent-green)";
        msgBox.style.border = "1px solid var(--accent-green)";
        msgBox.innerText = data.message;
        this.showToast(`New Member '${newUsername}' registered successfully!`);
        document.getElementById("newMemberUsername").value = "";
        document.getElementById("newMemberPassword").value = "";
        setTimeout(() => this.closeAddMemberModal(), 1800);
      } else {
        msgBox.style.display = "block";
        msgBox.style.background = "rgba(239, 68, 68, 0.15)";
        msgBox.style.color = "#ef4444";
        msgBox.style.border = "1px solid #ef4444";
        msgBox.innerText = data.message || "Failed to add member.";
      }
    } catch (e) {
      msgBox.style.display = "block";
      msgBox.style.background = "rgba(239, 68, 68, 0.15)";
      msgBox.style.color = "#ef4444";
      msgBox.style.border = "1px solid #ef4444";
      msgBox.innerText = "Error: " + e.message;
    }
  }

  // --- WORKFLOW & APP SERVICES ---
  async fetchWorkflows() {
    try {
      const res = await fetch("/api/workflows");
      const data = await res.json();
      if (data.status === "success") {
        this.workflows = data.workflows;
      }
    } catch (e) {
      console.error("Failed to load workflows:", e);
    }
  }

  switchTab(tab) {
    const sTab = document.getElementById("servicesTab");
    const pTab = document.getElementById("pdfEditorTab");
    const sBtn = document.getElementById("navServicesBtn");
    const pBtn = document.getElementById("navPdfEditorBtn");

    if (tab === "services") {
      sTab.style.display = "block";
      pTab.style.display = "none";
      sBtn.classList.add("active");
      pBtn.classList.remove("active");
    } else {
      sTab.style.display = "none";
      pTab.style.display = "block";
      sBtn.classList.remove("active");
      pBtn.classList.add("active");
    }
  }

  renderServices() {
    const grid = document.getElementById("serviceGrid");
    if (!grid) return;

    let html = this.workflows.map(wf => `
      <div class="service-card" onclick="docFlowApp.openWorkflow('${wf.id}')">
        <div>
          <div class="service-icon">
            <i class="fa-solid ${wf.icon}"></i>
          </div>
          <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.4rem;">${wf.title}</h3>
          <p style="font-size: 0.88rem; color: var(--text-muted); line-height: 1.4;">${wf.description}</p>
        </div>
        <div style="margin-top: 1.5rem; display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.8rem; font-weight: 600; color: var(--accent-blue);">${wf.documents.length} Required Files</span>
          <span class="btn-back" style="font-size: 0.8rem;">Start Workflow <i class="fa-solid fa-arrow-right"></i></span>
        </div>
      </div>
    `).join("");

    grid.innerHTML = html;
  }

  showHome() {
    document.getElementById("homeView").style.display = "block";
    document.getElementById("workflowView").style.display = "none";
    this.activeWf = null;
    this.uploadedFilesMap = {};
    this.transformParamsMap = {};
    this.processedFilesList = [];
    this.zipDownloadUrl = null;
  }

  openWorkflow(wfId) {
    const wf = this.workflows.find(w => w.id === wfId);
    if (!wf) return;

    this.activeWf = wf;
    this.uploadedFilesMap = {};
    this.transformParamsMap = {};
    this.processedFilesList = [];
    this.zipDownloadUrl = null;

    // Reset Form Fields to Blank
    document.getElementById("applicantName").value = "";
    document.getElementById("regNumber").value = "";
    document.getElementById("applicantDob").value = "";
    document.getElementById("applicantMobile").value = "";
    document.getElementById("applicantEmail").value = "";
    document.getElementById("applicantLoginId").value = "";
    document.getElementById("folderName").value = "";

    document.getElementById("homeView").style.display = "none";
    document.getElementById("workflowView").style.display = "block";
    document.getElementById("wfTitle").innerText = wf.title;
    document.getElementById("uploadLockBanner").style.display = "block";
    document.getElementById("applicantInfoCard").style.display = "none";
    document.getElementById("processingCard").style.display = "none";
    document.getElementById("resultCard").style.display = "none";

    this.renderDocUploadGrid();
  }

  renderDocUploadGrid() {
    const grid = document.getElementById("docUploadGrid");
    if (!grid || !this.activeWf) return;

    let html = this.activeWf.documents.map(doc => {
      if (doc.multi_side) {
        return `
          <div class="doc-card" id="card_${doc.id}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
              <h4 style="font-size: 1rem; font-weight: 700;">${doc.label}</h4>
              <span class="badge-status" id="badge_${doc.id}">Pending Both Sides</span>
            </div>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem;">${doc.hint}</p>
            
            <div style="display: flex; gap: 0.8rem; flex-wrap: wrap;">
              <div style="flex: 1; min-width: 140px;">
                <label style="font-size: 0.78rem; font-weight: 600; color: var(--text-bright);">Front Side</label>
                <div class="drop-zone" id="dz_${doc.id}_front" onclick="document.getElementById('input_${doc.id}_front').click()">
                  <i class="fa-solid fa-cloud-arrow-up" style="font-size: 1.4rem; color: var(--accent-blue);"></i>
                  <span id="label_${doc.id}_front" style="font-size: 0.78rem; display: block; margin-top: 0.4rem;">Select Front File</span>
                  <input type="file" id="input_${doc.id}_front" accept="image/*,application/pdf" style="display: none;" onchange="docFlowApp.handleFileSelect('${doc.id}', 'front', this.files)">
                </div>
                <div id="editor_btn_${doc.id}_front"></div>
              </div>

              <div style="flex: 1; min-width: 140px;">
                <label style="font-size: 0.78rem; font-weight: 600; color: var(--text-bright);">Back Side</label>
                <div class="drop-zone" id="dz_${doc.id}_back" onclick="document.getElementById('input_${doc.id}_back').click()">
                  <i class="fa-solid fa-cloud-arrow-up" style="font-size: 1.4rem; color: var(--accent-blue);"></i>
                  <span id="label_${doc.id}_back" style="font-size: 0.78rem; display: block; margin-top: 0.4rem;">Select Back File</span>
                  <input type="file" id="input_${doc.id}_back" accept="image/*,application/pdf" style="display: none;" onchange="docFlowApp.handleFileSelect('${doc.id}', 'back', this.files)">
                </div>
                <div id="editor_btn_${doc.id}_back"></div>
              </div>
            </div>
          </div>
        `;
      } else {
        return `
          <div class="doc-card" id="card_${doc.id}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
              <h4 style="font-size: 1rem; font-weight: 700;">${doc.label}</h4>
              <span class="badge-status" id="badge_${doc.id}">Pending</span>
            </div>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem;">${doc.hint}</p>

            <div class="drop-zone" id="dz_${doc.id}" onclick="document.getElementById('input_${doc.id}').click()">
              <i class="fa-solid fa-cloud-arrow-up" style="font-size: 1.8rem; color: var(--accent-blue);"></i>
              <span id="label_${doc.id}" style="font-size: 0.85rem; display: block; margin-top: 0.4rem;">Click to select file</span>
              <input type="file" id="input_${doc.id}" accept="image/*,application/pdf" style="display: none;" onchange="docFlowApp.handleFileSelect('${doc.id}', 'single', this.files)">
            </div>
            <div id="editor_btn_${doc.id}" style="text-align: center;"></div>
          </div>
        `;
      }
    }).join("");

    grid.innerHTML = html;
  }

  handleFileSelect(docId, mode, files) {
    if (!files || files.length === 0) return;
    const file = files[0];

    this.assignFileToSlot(docId, mode, file);
    this.checkAndUnlockApplicantForm();

    if (docId === "old_ppp_card" || docId === "reg_cert" || docId === "aadhaar") {
      this.runOcrExtraction(file);
    }
  }

  assignFileToSlot(docId, mode, file) {
    let slotId = docId;
    if (mode === "single") {
      this.uploadedFilesMap[docId] = file;
      document.getElementById(`label_${docId}`).innerText = `✓ ${file.name}`;
      document.getElementById(`badge_${docId}`).innerText = "Uploaded";
    } else if (mode === "front") {
      if (!this.uploadedFilesMap[docId]) this.uploadedFilesMap[docId] = {};
      this.uploadedFilesMap[docId].front = file;
      slotId = `${docId}_front`;
      document.getElementById(`label_${docId}_front`).innerText = `✓ Front (${file.name.substring(0, 14)}...)`;
    } else if (mode === "back") {
      if (!this.uploadedFilesMap[docId]) this.uploadedFilesMap[docId] = {};
      this.uploadedFilesMap[docId].back = file;
      slotId = `${docId}_back`;
      document.getElementById(`label_${docId}_back`).innerText = `✓ Back (${file.name.substring(0, 14)}...)`;
    }

    if (mode !== "single" && this.uploadedFilesMap[docId]?.front) {
      document.getElementById(`badge_${docId}`).innerText = "Ready";
    }

    this.transformParamsMap[slotId] = { angle: 0, flipH: false, flipV: false, freeAngle: 0.0, deblur: true, file: file };

    const container = document.getElementById(`editor_btn_${slotId}`);
    if (container) {
      container.innerHTML = `
        <button type="button" class="btn-back" style="font-size:0.75rem; padding:0.3rem 0.8rem; margin-top:0.3rem;" onclick="docFlowApp.openRotationModal('${slotId}')">
          <i class="fa-solid fa-sliders"></i> Open Editor Pop-up (0°)
        </button>
      `;
    }
  }

  checkAndUnlockApplicantForm() {
    if (!this.activeWf) return;
    let allReady = true;

    for (const doc of this.activeWf.documents) {
      const entry = this.uploadedFilesMap[doc.id];
      if (!entry) {
        allReady = false;
        break;
      }
      if (doc.multi_side && (!entry.front || !entry.back)) {
        allReady = false;
        break;
      }
    }

    if (allReady) {
      document.getElementById("uploadLockBanner").style.display = "none";
      document.getElementById("applicantInfoCard").style.display = "block";
      this.renderDocSummaryList();
      this.showToast("All document slots filled! Applicant Details Unlocked.");
    }
  }

  async runOcrExtraction(file) {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/extract_document_data", { method: "POST", body: formData });
      const data = await res.json();
      if (data.status === "success" && data.extracted) {
        const ext = data.extracted;
        if (ext.name) document.getElementById("applicantName").value = ext.name;
        if (ext.reg_number) document.getElementById("regNumber").value = ext.reg_number;
        if (ext.dob) document.getElementById("applicantDob").value = ext.dob;
        if (ext.mobile) document.getElementById("applicantMobile").value = ext.mobile;
        if (ext.email) document.getElementById("applicantEmail").value = ext.email;
        if (ext.login_id) document.getElementById("applicantLoginId").value = ext.login_id;
        
        if (ext.name) {
          let cleanName = ext.name.replace(/[^A-Za-z0-9]/g, '_');
          document.getElementById("folderName").value = `${cleanName}_PPP_Renewal`;
        }

        this.showToast("Auto-OCR recognized document data!");
      }
    } catch (e) {
      console.log("OCR Auto-extraction note:", e);
    }
  }

  renderDocSummaryList() {
    const list = document.getElementById("docSummaryList");
    if (!list || !this.activeWf) return;

    let html = this.activeWf.documents.map(doc => `
      <div class="summary-item">
        <div style="display: flex; align-items: center; gap: 0.6rem;">
          <i class="fa-solid fa-file-pdf" style="color: var(--accent-blue);"></i>
          <span style="font-size: 0.88rem; font-weight: 600;">${doc.output_name} (${doc.label})</span>
        </div>
        <span class="badge-status" style="background: rgba(59, 130, 246, 0.15); color: var(--accent-blue);">
          Target: < ${doc.max_kb} KB
        </span>
      </div>
    `).join("");

    list.innerHTML = html;
  }

  openMspcRedirectModal() {
    const name = document.getElementById("applicantName")?.value.trim() || "";
    const regNo = document.getElementById("regNumber")?.value.trim() || "";
    const dob = document.getElementById("applicantDob")?.value.trim() || "";
    const mobile = document.getElementById("applicantMobile")?.value.trim() || "";
    const email = document.getElementById("applicantEmail")?.value.trim() || "";

    let pass = "";
    if (name && dob) {
      let cleanName = name.replace(/[^A-Za-z]/g, '').toUpperCase();
      let prefix = cleanName.substring(0, 3);
      let dobParts = dob.split('/');
      let day = dobParts[0] || "01";
      let month = dobParts[1] || "01";
      pass = `${prefix}${day}${month}`;
    }

    document.getElementById("copyRegNo").innerText = regNo || "-";
    document.getElementById("copyDob").innerText = dob || "-";
    document.getElementById("copyMobile").innerText = mobile || "-";
    document.getElementById("copyEmail").innerText = email || "-";
    document.getElementById("copyPass").innerText = pass || "-";

    document.getElementById("mspcRedirectModal").style.display = "flex";
  }

  closeMspcRedirectModal() {
    document.getElementById("mspcRedirectModal").style.display = "none";
  }

  copyTextToClipboard(text) {
    if (!text || text === "-") return;
    navigator.clipboard.writeText(text).then(() => {
      this.showToast(`Copied "${text}" to clipboard! Paste it on MSPC Portal.`);
    }).catch(err => {
      console.error("Clipboard copy error:", err);
    });
  }

  showToast(msg) {
    const toast = document.createElement("div");
    toast.style.position = "fixed";
    toast.style.bottom = "20px";
    toast.style.right = "20px";
    toast.style.background = "linear-gradient(135deg, #8b5cf6, #3b82f6)";
    toast.style.color = "#fff";
    toast.style.padding = "0.8rem 1.2rem";
    toast.style.borderRadius = "8px";
    toast.style.boxShadow = "0 10px 25px rgba(0,0,0,0.3)";
    toast.style.zIndex = "99999";
    toast.style.fontWeight = "600";
    toast.style.fontSize = "0.88rem";
    toast.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${msg}`;

    document.body.appendChild(toast);
    setTimeout(() => {
      if (document.body.contains(toast)) {
        document.body.removeChild(toast);
      }
    }, 4000);
  }

  // --- POP-UP LIVE IMAGE EDITOR ---
  async openRotationModal(slotId) {
    const params = this.transformParamsMap[slotId];
    if (!params || !params.file) return;

    this.modalSlotId = slotId;
    this.modalFile = params.file;

    document.getElementById("rotationEditorModal").style.display = "flex";
    document.getElementById("freeAngleSlider").value = params.freeAngle || 0;
    document.getElementById("freeAngleValue").innerText = `${params.freeAngle || 0}°`;

    const formData = new FormData();
    formData.append("file", this.modalFile);
    const res = await fetch("/api/preview_rotation", { method: "POST", body: formData });
    const data = await res.json();

    if (data.status === "success") {
      document.getElementById("modalRawImg").src = data.raw_image;
    }

    this.triggerModalLiveRender();
  }

  closeRotationModal() {
    document.getElementById("rotationEditorModal").style.display = "none";
    this.modalSlotId = null;
    this.modalFile = null;
  }

  async triggerModalLiveRender() {
    if (!this.modalSlotId || !this.modalFile) return;

    const params = this.transformParamsMap[this.modalSlotId];
    const liveImg = document.getElementById("modalLivePreviewImg");

    const formData = new FormData();
    formData.append("file", this.modalFile);
    formData.append("angle", params.angle);
    formData.append("flip_h", params.flipH);
    formData.append("flip_v", params.flipV);
    formData.append("free_angle", params.freeAngle);
    formData.append("deblur", params.deblur);

    try {
      const res = await fetch("/api/live_render", { method: "POST", body: formData });
      const data = await res.json();
      if (data.status === "success") {
        liveImg.src = data.preview;
      }
    } catch (e) {
      console.error("Live render error:", e);
    }
  }

  modalRotateAngle(delta) {
    if (!this.modalSlotId) return;
    const params = this.transformParamsMap[this.modalSlotId];
    params.angle = (params.angle + delta + 360) % 360;
    this.triggerModalLiveRender();
  }

  modalFlip(direction) {
    if (!this.modalSlotId) return;
    const params = this.transformParamsMap[this.modalSlotId];
    if (direction === 'h') params.flipH = !params.flipH;
    if (direction === 'v') params.flipV = !params.flipV;
    this.triggerModalLiveRender();
  }

  modalToggleDebblur() {
    if (!this.modalSlotId) return;
    const params = this.transformParamsMap[this.modalSlotId];
    params.deblur = !params.deblur;
    this.triggerModalLiveRender();
  }

  updateFreeAngleSlider(val) {
    if (!this.modalSlotId) return;
    const params = this.transformParamsMap[this.modalSlotId];
    params.freeAngle = parseFloat(val);
    document.getElementById("freeAngleValue").innerText = `${val}°`;
    this.triggerModalLiveRender();
  }

  modalReset() {
    if (!this.modalSlotId) return;
    const params = this.transformParamsMap[this.modalSlotId];
    params.angle = 0;
    params.flipH = false;
    params.flipV = false;
    params.freeAngle = 0.0;
    params.deblur = true;
    document.getElementById("freeAngleSlider").value = 0;
    document.getElementById("freeAngleValue").innerText = "0°";
    this.triggerModalLiveRender();
  }

  confirmModalRotation() {
    if (this.modalSlotId) {
      const params = this.transformParamsMap[this.modalSlotId];
      const container = document.getElementById(`editor_btn_${this.modalSlotId}`);
      if (container) {
        container.innerHTML = `
          <button type="button" class="btn-back" style="font-size:0.75rem; padding:0.3rem 0.8rem; margin-top:0.3rem;" onclick="docFlowApp.openRotationModal('${this.modalSlotId}')">
            <i class="fa-solid fa-sliders"></i> Open Editor Pop-up (${params.angle}°)
          </button>
        `;
      }
    }
    this.closeRotationModal();
  }

  // --- WORKFLOW PROCESSING ---
  async processWorkflow() {
    if (!this.activeWf) return;

    const applicantName = document.getElementById("applicantName").value.trim() || "Applicant";
    const regNumber = document.getElementById("regNumber").value.trim() || "000000";
    const loginId = document.getElementById("applicantLoginId").value.trim() || `MSPC${regNumber}`;
    const dob = document.getElementById("applicantDob").value.trim() || "01/01/2000";
    const mobile = document.getElementById("applicantMobile").value.trim() || "0000000000";
    const email = document.getElementById("applicantEmail").value.trim() || "applicant@docflow.org";
    const folderName = document.getElementById("folderName").value.trim() || `${applicantName}_Package`;

    const processBtn = document.getElementById("processBtn");
    const processingCard = document.getElementById("processingCard");
    const resultCard = document.getElementById("resultCard");

    processBtn.disabled = true;
    processingCard.style.display = "block";
    resultCard.style.display = "none";

    const formData = new FormData();
    formData.append("workflow_id", this.activeWf.id);
    formData.append("applicant_name", applicantName);
    formData.append("reg_number", regNumber);
    formData.append("login_id", loginId);
    formData.append("dob", dob);
    formData.append("email", email);
    formData.append("mobile", mobile);
    formData.append("folder_name", folderName);

    for (const doc of this.activeWf.documents) {
      const entry = this.uploadedFilesMap[doc.id];
      if (doc.multi_side && entry) {
        if (entry.front) {
          const slot = `${doc.id}_front`;
          const params = this.transformParamsMap[slot] || { angle: 0, flipH: false, flipV: false };
          formData.append(`${doc.id}_front`, entry.front);
          formData.append(`rot_${doc.id}_front`, params.angle);
          formData.append(`fliph_${doc.id}_front`, params.flipH);
          formData.append(`flipv_${doc.id}_front`, params.flipV);
        }
        if (entry.back) {
          const slot = `${doc.id}_back`;
          const params = this.transformParamsMap[slot] || { angle: 0, flipH: false, flipV: false };
          formData.append(`${doc.id}_back`, entry.back);
          formData.append(`rot_${doc.id}_back`, params.angle);
          formData.append(`fliph_${doc.id}_back`, params.flipH);
          formData.append(`flipv_${doc.id}_back`, params.flipV);
        }
      } else if (entry) {
        const params = this.transformParamsMap[doc.id] || { angle: 0, flipH: false, flipV: false };
        formData.append(doc.id, entry);
        formData.append(`rot_${doc.id}`, params.angle);
        formData.append(`fliph_${doc.id}`, params.flipH);
        formData.append(`flipv_${doc.id}`, params.flipV);
      }
    }

    try {
      const res = await fetch("/api/process_workflow", { method: "POST", body: formData });
      const data = await res.json();

      processingCard.style.display = "none";

      if (data.status === "success") {
        this.processedFilesList = data.files;
        this.zipDownloadUrl = data.zip_download_url;

        resultCard.style.display = "block";

        const zipBtn = document.getElementById("zipDownloadBtn");
        zipBtn.href = data.zip_download_url;
        zipBtn.download = data.zip_filename;
        document.getElementById("zipFileNameLabel").innerText = data.zip_filename;
        document.getElementById("zipFileSizeLabel").innerText = `Package Size: ${data.zip_size_kb} KB`;

        if (data.mspc_credentials) {
          const c = data.mspc_credentials;
          document.getElementById("resApplicantName").innerText = c.applicant_name;
          document.getElementById("resLoginId").innerText = c.login_id;
          document.getElementById("resMspcPass").innerText = c.password;
          document.getElementById("resRegNo").innerText = c.reg_number;
          document.getElementById("resDob").innerText = c.dob;
          document.getElementById("resMobile").innerText = c.mobile;
          document.getElementById("resEmail").innerText = c.email;
          document.getElementById("resGenDate").innerText = c.generated_date;
        }

        const listContainer = document.getElementById("processedFilesList");
        listContainer.innerHTML = data.files.map(f => `
          <div class="summary-item">
            <div>
              <strong>${f.filename}</strong> (${f.label})
              <div style="font-size: 0.8rem; color: var(--text-muted);">${f.status}</div>
            </div>
            <a href="${f.download_url}" download class="btn-back" style="font-size: 0.8rem; padding: 0.3rem 0.7rem;">
              <i class="fa-solid fa-download"></i> Download
            </a>
          </div>
        `).join("");

        this.showToast("Workflow completed successfully! Download ZIP ready.");
      } else {
        alert("Workflow Error: " + data.message);
      }
    } catch (e) {
      processingCard.style.display = "none";
      alert("Processing Exception: " + e.message);
    } finally {
      processBtn.disabled = false;
    }
  }
}

const docFlowApp = new DocFlowApp();
