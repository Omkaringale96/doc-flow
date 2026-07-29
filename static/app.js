/* ==========================================================================
   DocFlow Pro - Frontend Engine with Ordered Credentials & Direct ZIP File Download
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

    this.init();
  }

  async init() {
    await this.fetchWorkflows();
    this.renderServices();
  }

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
      sBtn.style.background = "var(--bg-card-hover)";
      pBtn.style.background = "var(--bg-card)";
    } else {
      sTab.style.display = "none";
      pTab.style.display = "block";
      sBtn.style.background = "var(--bg-card)";
      pBtn.style.background = "var(--bg-card-hover)";
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

    document.getElementById("homeView").style.display = "none";
    document.getElementById("workflowView").style.display = "block";
    document.getElementById("wfTitle").innerText = wf.title;
    document.getElementById("resultsSection").style.display = "none";
    document.getElementById("mspcCard").style.display = "none";
    document.getElementById("stepTracker").style.display = "none";

    document.getElementById("uploadLockBanner").style.display = "block";
    document.getElementById("applicantInfoCard").style.display = "none";
    document.getElementById("processActionBox").style.display = "none";

    this.renderDocCards(wf);
  }

  renderDocCards(wf) {
    const grid = document.getElementById("docUploadGrid");
    if (!grid) return;

    grid.innerHTML = wf.documents.map(doc => {
      if (doc.multi_side) {
        return `
          <div class="doc-card" id="card_${doc.id}">
            <div>
              <div class="doc-card-header">
                <span class="doc-title">${doc.label}</span>
                <span class="badge-status" id="badge_${doc.id}">Pending</span>
              </div>
              <p class="doc-hint">${doc.hint}</p>
            </div>

            <div style="display: flex; gap: 0.6rem; margin-top: 0.8rem;">
              <div style="flex:1;">
                <div class="doc-upload-box" onclick="docFlowApp.triggerFileSelect('${doc.id}_front')">
                  <i class="fa-solid fa-file-image"></i>
                  <div style="font-size: 0.8rem; font-weight:600;" id="label_${doc.id}_front">Upload Front</div>
                  <input type="file" id="input_${doc.id}_front" style="display:none" onchange="docFlowApp.handleFilePicked('${doc.id}', 'front', this)">
                </div>
                <div id="editor_btn_${doc.id}_front" style="margin-top:0.4rem; text-align:center;"></div>
              </div>

              <div style="flex:1;">
                <div class="doc-upload-box" onclick="docFlowApp.triggerFileSelect('${doc.id}_back')">
                  <i class="fa-solid fa-file-image"></i>
                  <div style="font-size: 0.8rem; font-weight:600;" id="label_${doc.id}_back">Upload Back</div>
                  <input type="file" id="input_${doc.id}_back" style="display:none" onchange="docFlowApp.handleFilePicked('${doc.id}', 'back', this)">
                </div>
                <div id="editor_btn_${doc.id}_back" style="margin-top:0.4rem; text-align:center;"></div>
              </div>
            </div>
          </div>
        `;
      }

      return `
        <div class="doc-card" id="card_${doc.id}">
          <div>
            <div class="doc-card-header">
              <span class="doc-title">${doc.label}</span>
              <span class="badge-status" id="badge_${doc.id}">Pending</span>
            </div>
            <p class="doc-hint">${doc.hint}</p>
          </div>

          <div class="doc-upload-box" onclick="docFlowApp.triggerFileSelect('${doc.id}')">
            <i class="fa-solid fa-cloud-arrow-up" style="font-size: 1.5rem; color: var(--accent-blue);"></i>
            <div style="font-size: 0.85rem; font-weight:600; margin-top:0.4rem;" id="label_${doc.id}">Click or Drag File Here</div>
            <input type="file" id="input_${doc.id}" style="display:none" onchange="docFlowApp.handleFilePicked('${doc.id}', 'single', this)">
          </div>
          <div id="editor_btn_${doc.id}" style="margin-top:0.4rem; text-align:center;"></div>
        </div>
      `;
    }).join("");
  }

  triggerFileSelect(inputId) {
    document.getElementById(`input_${inputId}`)?.click();
  }

  handleFilePicked(docId, mode, inputEl) {
    if (!inputEl.files || !inputEl.files[0]) return;
    const file = inputEl.files[0];
    this.assignFileToSlot(docId, mode, file);

    // Run OCR Data Extractor on document upload
    if (docId === 'reg_cert' || docId === 'old_ppp_card' || docId === 'aadhaar') {
      this.extractDataFromDocument(file);
    }

    this.checkAllDocsUploaded();
  }

  checkAllDocsUploaded() {
    if (!this.activeWf) return;

    let allReady = true;
    for (const doc of this.activeWf.documents) {
      const entry = this.uploadedFilesMap[doc.id];
      if (doc.multi_side) {
        if (!entry || (!entry.front && !entry.back)) {
          allReady = false;
          break;
        }
      } else {
        if (!entry) {
          allReady = false;
          break;
        }
      }
    }

    if (allReady) {
      document.getElementById("uploadLockBanner").style.display = "none";
      document.getElementById("applicantInfoCard").style.display = "block";
      document.getElementById("processActionBox").style.display = "block";

      this.showToast("✨ All documents uploaded! Applicant Info unlocked & auto-filled via OCR.");
    }
  }

  async extractDataFromDocument(file) {
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/extract_document_data", { method: "POST", body: formData });
      const data = await res.json();

      if (data.status === "success" && data.extracted) {
        const ext = data.extracted;
        if (ext.name) document.getElementById("applicantName").value = ext.name;
        if (ext.reg_number) {
          document.getElementById("applicantRegNumber").value = ext.reg_number;
          document.getElementById("applicantLoginId").value = `MSPC${ext.reg_number}`;
        }
        if (ext.dob) document.getElementById("applicantDob").value = ext.dob;
        if (ext.mobile) document.getElementById("applicantMobile").value = ext.mobile;
        if (ext.email) document.getElementById("applicantEmail").value = ext.email;

        const cleanName = ext.name.replace(/[^A-Za-z0-9]/g, '_');
        document.getElementById("folderNameInput").value = `${cleanName}_PPP_Renewal`;
      }
    } catch (e) {
      console.log("OCR Auto-extraction note:", e);
    }
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

  // --- MSPC PORTAL DIRECT REDIRECT & DEDICATED EMAIL QUICK COPY MODAL ---
  openMspcPortalRedirectModal() {
    const name = document.getElementById("applicantName")?.value || "VINAYAK PATIL";
    const regNo = document.getElementById("applicantRegNumber")?.value || "189423";
    const dob = document.getElementById("applicantDob")?.value || "21/06/2004";
    const mobile = document.getElementById("applicantMobile")?.value || "9876543210";
    const email = document.getElementById("applicantEmail")?.value || "vinayak@gmail.com";

    // Compute Password (VIN2106)
    let cleanName = name.replace(/[^A-Za-z]/g, '').toUpperCase();
    let prefix = cleanName.substring(0, 3) || "VIN";
    let dobParts = dob.split('/');
    let day = dobParts[0] || "21";
    let month = dobParts[1] || "06";
    let pass = `${prefix}${day}${month}`;

    document.getElementById("copyRegNo").innerText = regNo;
    document.getElementById("copyName").innerText = name;
    document.getElementById("copyDob").innerText = dob;
    document.getElementById("copyMobile").innerText = mobile;
    document.getElementById("copyEmail").innerText = email;
    document.getElementById("copyPass").innerText = pass;

    document.getElementById("mspcRedirectModal").style.display = "flex";
  }

  closeMspcRedirectModal() {
    document.getElementById("mspcRedirectModal").style.display = "none";
  }

  copyTextToClipboard(text) {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      this.showToast(`Copied "${text}" to clipboard! Now paste it on MSPC Portal.`);
    }).catch(err => {
      console.error("Clipboard copy error:", err);
    });
  }

  // --- POP-UP EDITOR MODAL WINDOW ---
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

  // --- WORKFLOW PROCESSING & DIRECT ZIP FILE GENERATION ---
  async processWorkflow() {
    if (!this.activeWf) return;

    const applicantName = document.getElementById("applicantName").value || "VINAYAK PATIL";
    const regNumber = document.getElementById("applicantRegNumber").value || "189423";
    const loginId = document.getElementById("applicantLoginId").value || `MSPC${regNumber}`;
    const dob = document.getElementById("applicantDob").value || "21/06/2004";
    const mobile = document.getElementById("applicantMobile").value || "9876543210";
    const email = document.getElementById("applicantEmail").value || "vinayak@gmail.com";
    const folderName = document.getElementById("folderNameInput").value || "Vinayak_Patil_PPP_Renewal";

    const btn = document.getElementById("startProcessBtn");
    const statusText = document.getElementById("progressStatusText");
    const stepTracker = document.getElementById("stepTracker");

    btn.disabled = true;
    stepTracker.style.display = "flex";

    const steps = [
      { id: "step1", text: "1. MSPC Login & Password Calculation..." },
      { id: "step2", text: "2. Verifying orientation (0° Default)..." },
      { id: "step3", text: "3. Applying image deblur filter..." },
      { id: "step4", text: "4. Resizing photo (160x160) & signature canvas (160x40)..." },
      { id: "step5", text: "5. Strict compression (<100KB PDF, <20KB JPG)..." },
      { id: "step6", text: "6. Building Output ZIP File..." }
    ];

    for (let i = 0; i < steps.length; i++) {
      const s = steps[i];
      statusText.innerText = s.text;
      document.querySelectorAll(".step-item").forEach(item => item.classList.remove("active"));
      document.getElementById(s.id)?.classList.add("active");
      await new Promise(r => setTimeout(r, 400));
    }

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
      if (data.status === "success") {
        this.processedFilesList = data.files;
        this.zipDownloadUrl = data.zip_download_url;

        document.getElementById("resultsSection").style.display = "block";

        // Configure Primary ZIP File Download Button
        const zipBtn = document.getElementById("mainZipDownloadBtn");
        zipBtn.href = data.zip_download_url;
        zipBtn.download = data.zip_filename;
        document.getElementById("zipBtnLabel").innerText = `Download ${data.zip_filename} (${data.zip_size_kb} KB)`;

        if (data.mspc_credentials) {
          const c = data.mspc_credentials;
          document.getElementById("mspcCard").style.display = "block";
          document.getElementById("mspcApplicantName").innerText = c.applicant_name;
          document.getElementById("mspcLoginId").innerText = c.login_id;
          document.getElementById("mspcPass").innerText = c.password;
          document.getElementById("mspcRegNo").innerText = c.reg_number;
          document.getElementById("mspcDob").innerText = c.dob;
          document.getElementById("mspcMobile").innerText = c.mobile;
          document.getElementById("mspcEmail").innerText = c.email;
          document.getElementById("mspcGenDate").innerText = c.generated_date;
        }

        statusText.innerText = `✓ Output ZIP File (${data.zip_filename}) Generated Successfully!`;
      } else {
        alert("Error: " + data.message);
        statusText.innerText = "Processing error";
      }
    } catch (e) {
      alert("Error: " + e.message);
      statusText.innerText = "Failed";
    } finally {
      btn.disabled = false;
    }
  }
}

const docFlowApp = new DocFlowApp();
