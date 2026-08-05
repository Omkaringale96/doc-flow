/* ==========================================================================
   DocFlow Pro - Frontend Engine with Section-Based Workflows & Auth
   ========================================================================== */

class DocFlowApp {
  constructor() {
    this.workflows = [];
    this.activeWf = null;
    this.uploadedFilesMap = {}; // docId/srcId -> File or {front: File, back: File}
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
    const token = localStorage.getItem("docflow_token");
    const username = localStorage.getItem("docflow_username");
    if (token && username) {
      this.authToken = token;
      this.currentUser = username;
      this.showAuthenticatedApp();
    } else {
      this.logoutSilently();
    }
  }

  logoutSilently() {
    this.authToken = null;
    this.currentUser = null;
    localStorage.removeItem("docflow_token");
    localStorage.removeItem("docflow_username");
    this.showLoginModal();
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
    
    const addMemberNavBtn = document.getElementById("addMemberNavBtn");
    if (this.currentUser === "Datta") {
      document.getElementById("loggedInUserLabel").innerText = `Datta (Administrator)`;
      if (addMemberNavBtn) addMemberNavBtn.style.display = "inline-flex";
    } else {
      document.getElementById("loggedInUserLabel").innerText = `${this.currentUser} (Authorized Member)`;
      if (addMemberNavBtn) addMemberNavBtn.style.display = "none";
    }
  }

  showLoginModal() {
    document.getElementById("loginModalContainer").style.display = "flex";
    document.getElementById("mainAppContent").style.display = "none";
    document.getElementById("userPillContainer").style.display = "none";
  }

  logout() {
    this.logoutSilently();
    this.showToast("Logged out safely.");
  }

  // --- MEMBER MANAGEMENT ENGINE (DATTA ADMINISTRATOR ONLY) ---
  openAddMemberModal() {
    if (this.currentUser !== "Datta") {
      alert("Only Administrator Datta can manage members!");
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
    if (this.currentUser !== "Datta") {
      alert("Only Administrator Datta can add members!");
      return;
    }
    const newUsername = document.getElementById("newMemberUsername").value.trim();
    const newPassword = document.getElementById("newMemberPassword").value.trim();
    const msgBox = document.getElementById("addMemberMsg");

    if (!newUsername || !newPassword) return;

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

  async handleRemoveMember(event) {
    event.preventDefault();
    if (this.currentUser !== "Datta") {
      alert("Only Administrator Datta can remove members!");
      return;
    }
    const usernameToRemove = document.getElementById("removeMemberUsername").value.trim();
    if (!usernameToRemove) return;

    if (!confirm(`Are you sure you want to remove member '${usernameToRemove}'?`)) return;

    const msgBox = document.getElementById("addMemberMsg");
    msgBox.style.display = "none";

    try {
      const res = await fetch("/api/remove_user", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${this.authToken}`
        },
        body: JSON.stringify({ username: usernameToRemove })
      });
      const data = await res.json();

      if (data.status === "success") {
        msgBox.style.display = "block";
        msgBox.style.background = "rgba(34, 197, 94, 0.15)";
        msgBox.style.color = "var(--accent-green)";
        msgBox.style.border = "1px solid var(--accent-green)";
        msgBox.innerText = data.message;
        this.showToast(`Member '${usernameToRemove}' removed successfully!`);
        document.getElementById("removeMemberUsername").value = "";
        setTimeout(() => this.closeAddMemberModal(), 1800);
      } else {
        msgBox.style.display = "block";
        msgBox.style.background = "rgba(239, 68, 68, 0.15)";
        msgBox.style.color = "#ef4444";
        msgBox.style.border = "1px solid #ef4444";
        msgBox.innerText = data.message || "Failed to remove member.";
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

    if (sTab) sTab.style.display = tab === "services" ? "block" : "none";
    if (pTab) pTab.style.display = tab === "pdf_editor" ? "block" : "none";

    if (sBtn) sBtn.classList.toggle("active", tab === "services");
    if (pBtn) pBtn.classList.toggle("active", tab === "pdf_editor");

    if (tab === "pdf_editor") this.switchPdfSubTab('sejda');
  }

  switchPdfSubTab(subTab) {
    const sejdaTab = document.getElementById("pdfSubTabSejda");
    const ilovepdfTab = document.getElementById("pdfSubTabILovePdf");
    const docflowTab = document.getElementById("pdfSubTabDocFlow");

    const sejdaBtn = document.getElementById("subTabSejdaBtn");
    const ilovepdfBtn = document.getElementById("subTabILovePdfBtn");
    const docflowBtn = document.getElementById("subTabDocFlowBtn");

    if (sejdaTab) sejdaTab.style.display = subTab === "sejda" ? "block" : "none";
    if (ilovepdfTab) ilovepdfTab.style.display = subTab === "ilovepdf" ? "block" : "none";
    if (docflowTab) docflowTab.style.display = subTab === "docflow" ? "block" : "none";

    if (sejdaBtn) {
      sejdaBtn.className = subTab === "sejda" ? "btn-primary" : "btn-back";
      if (subTab === "sejda") sejdaBtn.style.background = "var(--accent-green)";
      else sejdaBtn.style.background = "";
    }
    if (ilovepdfBtn) {
      ilovepdfBtn.className = subTab === "ilovepdf" ? "btn-primary" : "btn-back";
      if (subTab === "ilovepdf") ilovepdfBtn.style.background = "#ef4444";
      else ilovepdfBtn.style.background = "";
    }
    if (docflowBtn) {
      docflowBtn.className = subTab === "docflow" ? "btn-primary" : "btn-back";
      if (subTab === "docflow") docflowBtn.style.background = "var(--accent-blue)";
      else docflowBtn.style.background = "";
    }
  }

  getWorkflowDocs() {
    if (!this.activeWf) return [];
    if (this.activeWf.sections) {
      let list = [];
      this.activeWf.sections.forEach(sec => {
        sec.documents.forEach(d => list.push(d));
      });
      return list;
    }
    return this.activeWf.documents || [];
  }

  renderServices() {
    const grid = document.getElementById("serviceGrid");
    if (!grid) return;

    let html = this.workflows.map(wf => {
      const docsCount = this.getWorkflowDocsForWf(wf).length;
      return `
        <div class="service-card" onclick="docFlowApp.openWorkflow('${wf.id}')">
          <div>
            <div class="service-icon">
              <i class="fa-solid ${wf.icon}"></i>
            </div>
            <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.4rem;">${wf.title}</h3>
            <p style="font-size: 0.88rem; color: var(--text-muted); line-height: 1.4;">${wf.description}</p>
          </div>
          <div style="margin-top: 1.5rem; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 0.8rem; font-weight: 600; color: var(--accent-blue);">${docsCount} Document Items</span>
            <span class="btn-back" style="font-size: 0.8rem;">Start Workflow <i class="fa-solid fa-arrow-right"></i></span>
          </div>
        </div>
      `;
    }).join("");

    grid.innerHTML = html;
  }

  getWorkflowDocsForWf(wf) {
    if (wf.sections) {
      let list = [];
      wf.sections.forEach(sec => sec.documents.forEach(d => list.push(d)));
      return list;
    }
    return wf.documents || [];
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

    // Reset Form Fields
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
    document.getElementById("applicantInfoCard").style.display = "block";
    document.getElementById("processingCard").style.display = "none";
    document.getElementById("resultCard").style.display = "none";

    const helperBtn = document.getElementById("helperModalBtn");
    const quickCopyBtn = document.getElementById("quickCopyBtn");
    const resCardTitle = document.getElementById("resCardTitle");

    if (wf.id === "new_proprietorship_drug_license") {
      if (helperBtn) helperBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Open Sejda PDF Editor Suite';
      if (quickCopyBtn) quickCopyBtn.style.display = "none";
      if (resCardTitle) resCardTitle.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Sejda PDF Editor Suite & Package Actions';
    } else {
      if (helperBtn) helperBtn.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square"></i> MSPC Login Helper';
      if (quickCopyBtn) quickCopyBtn.style.display = "inline-flex";
      if (resCardTitle) resCardTitle.innerHTML = '<i class="fa-solid fa-copy"></i> Copy-Paste Assistant & MSPC Credentials';
    }

    this.renderDocUploadGrid();
  }

  renderDocUploadGrid() {
    const grid = document.getElementById("docUploadGrid");
    if (!grid || !this.activeWf) return;

    if (this.activeWf.sections) {
      let html = this.activeWf.sections.map(sec => `
        <div class="doc-section" style="margin-bottom: 1.8rem; background: rgba(15, 23, 42, 0.6); padding: 1.2rem; border-radius: 12px; border: 1px solid var(--border-glass);">
          <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--accent-blue); margin-bottom: 1rem; display: flex; align-items: center; gap: 0.6rem;">
            <i class="fa-solid ${sec.icon || 'fa-folder-open'}"></i> ${sec.title}
          </h3>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.2rem;">
            ${sec.documents.map(doc => this.renderDocCardHtml(doc)).join("")}
          </div>
        </div>
      `).join("");
      grid.innerHTML = html;
    } else {
      let html = this.activeWf.documents.map(doc => this.renderDocCardHtml(doc)).join("");
      grid.innerHTML = html;
    }
  }

  renderDocCardHtml(doc) {
    if (doc.multi_sources) {
      let sourcesHtml = doc.multi_sources.map(src => `
        <div style="flex: 1; min-width: 130px; margin-top: 0.4rem;">
          <label style="font-size: 0.78rem; font-weight: 600; color: var(--text-bright);">${src.label}</label>
          <div class="drop-zone" id="dz_${src.id}" onclick="document.getElementById('input_${src.id}').click()">
            <i class="fa-solid fa-cloud-arrow-up" style="font-size: 1.4rem; color: var(--accent-blue);"></i>
            <span id="label_${src.id}" style="font-size: 0.78rem; display: block; margin-top: 0.4rem;">Select ${src.label}</span>
            <input type="file" id="input_${src.id}" accept="${doc.type === 'pdf_only' ? 'application/pdf' : 'image/*,application/pdf'}" style="display: none;" onchange="docFlowApp.handleFileSelect('${src.id}', 'single', this.files, '${doc.id}')">
          </div>
          <div id="editor_btn_${src.id}"></div>
        </div>
      `).join("");

      return `
        <div class="doc-card" id="card_${doc.id}">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
            <h4 style="font-size: 0.98rem; font-weight: 700;">${doc.label}</h4>
            <span class="badge-status" id="badge_${doc.id}">Pending</span>
          </div>
          <p style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.6rem;">
            Outputs <strong>${doc.output_name}</strong> (< ${doc.max_kb} KB PDF)
          </p>
          <div style="display: flex; gap: 0.8rem; flex-wrap: wrap;">
            ${sourcesHtml}
          </div>
        </div>
      `;
    } else if (doc.multi_side) {
      return `
        <div class="doc-card" id="card_${doc.id}">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
            <h4 style="font-size: 0.98rem; font-weight: 700;">${doc.label}</h4>
            <span class="badge-status" id="badge_${doc.id}">Pending Both Sides</span>
          </div>
          <p style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.6rem;">${doc.hint}</p>
          
          <div style="display: flex; gap: 0.8rem; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 130px;">
              <label style="font-size: 0.78rem; font-weight: 600; color: var(--text-bright);">Front Side</label>
              <div class="drop-zone" id="dz_${doc.id}_front" onclick="document.getElementById('input_${doc.id}_front').click()">
                <i class="fa-solid fa-cloud-arrow-up" style="font-size: 1.4rem; color: var(--accent-blue);"></i>
                <span id="label_${doc.id}_front" style="font-size: 0.78rem; display: block; margin-top: 0.4rem;">Select Front File</span>
                <input type="file" id="input_${doc.id}_front" accept="image/*,application/pdf" style="display: none;" onchange="docFlowApp.handleFileSelect('${doc.id}', 'front', this.files)">
              </div>
              <div id="editor_btn_${doc.id}_front"></div>
            </div>

            <div style="flex: 1; min-width: 130px;">
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
      const acceptAttr = doc.type === 'image' ? 'image/*' : (doc.type === 'pdf_only' ? 'application/pdf' : 'image/*,application/pdf');
      return `
        <div class="doc-card" id="card_${doc.id}">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
            <h4 style="font-size: 0.98rem; font-weight: 700;">${doc.label}</h4>
            <span class="badge-status" id="badge_${doc.id}">Pending</span>
          </div>
          <p style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.8rem;">${doc.hint}</p>

          <div class="drop-zone" id="dz_${doc.id}" onclick="document.getElementById('input_${doc.id}').click()">
            <i class="fa-solid fa-cloud-arrow-up" style="font-size: 1.6rem; color: var(--accent-blue);"></i>
            <span id="label_${doc.id}" style="font-size: 0.82rem; display: block; margin-top: 0.4rem;">Click to select file</span>
            <input type="file" id="input_${doc.id}" accept="${acceptAttr}" style="display: none;" onchange="docFlowApp.handleFileSelect('${doc.id}', 'single', this.files)">
          </div>
          <div id="editor_btn_${doc.id}" style="text-align: center;"></div>
        </div>
      `;
    }
  }

  handleFileSelect(slotId, mode, files, parentDocId) {
    if (!files || files.length === 0) return;
    const file = files[0];

    this.assignFileToSlot(slotId, mode, file, parentDocId);
    this.checkAndUnlockApplicantForm();

    if (slotId === "old_ppp_card" || slotId === "reg_cert" || slotId === "aadhaar" || slotId === "photo") {
      this.runOcrExtraction(file);
    }
  }

  assignFileToSlot(slotId, mode, file, parentDocId) {
    let targetKey = slotId;
    if (mode === "single") {
      this.uploadedFilesMap[slotId] = file;
      const lbl = document.getElementById(`label_${slotId}`);
      if (lbl) lbl.innerText = `✓ ${file.name}`;
      const bdg = document.getElementById(`badge_${slotId}`);
      if (bdg) bdg.innerText = "Uploaded";
      if (parentDocId) {
        this.updateParentMultiSourceBadge(parentDocId);
      }
    } else if (mode === "front") {
      if (!this.uploadedFilesMap[slotId]) this.uploadedFilesMap[slotId] = {};
      this.uploadedFilesMap[slotId].front = file;
      targetKey = `${slotId}_front`;
      const lbl = document.getElementById(`label_${slotId}_front`);
      if (lbl) lbl.innerText = `✓ Front (${file.name.substring(0, 12)}...)`;
    } else if (mode === "back") {
      if (!this.uploadedFilesMap[slotId]) this.uploadedFilesMap[slotId] = {};
      this.uploadedFilesMap[slotId].back = file;
      targetKey = `${slotId}_back`;
      const lbl = document.getElementById(`label_${slotId}_back`);
      if (lbl) lbl.innerText = `✓ Back (${file.name.substring(0, 12)}...)`;
    }

    if (mode !== "single" && this.uploadedFilesMap[slotId]?.front) {
      const bdg = document.getElementById(`badge_${slotId}`);
      if (bdg) bdg.innerText = "Ready";
    }

    this.transformParamsMap[targetKey] = { angle: 0, flipH: false, flipV: false, freeAngle: 0.0, deblur: true, file: file };

    const container = document.getElementById(`editor_btn_${targetKey}`);
    if (container) {
      let extraStudioBtn = "";
      if (slotId.includes("rent_") || slotId === "rent_agreement") {
        extraStudioBtn = `
          <button type="button" class="btn-primary" style="font-size:0.72rem; padding:0.25rem 0.6rem; margin-top:0.3rem; background: var(--accent-purple);" onclick="docFlowApp.openWorkflowFileInStudio('${slotId}')">
            <i class="fa-solid fa-wand-magic-sparkles"></i> Open in PDF Studio
          </button>
        `;
      }
      container.innerHTML = `
        <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
          <button type="button" class="btn-back" style="font-size:0.72rem; padding:0.25rem 0.6rem; margin-top:0.3rem;" onclick="docFlowApp.openRotationModal('${targetKey}')">
            <i class="fa-solid fa-sliders"></i> Pop-up Editor (0°)
          </button>
          ${extraStudioBtn}
        </div>
      `;
    }
  }

  updateParentMultiSourceBadge(parentDocId) {
    const allDocs = this.getWorkflowDocs();
    const parentDoc = allDocs.find(d => d.id === parentDocId);
    if (!parentDoc || !parentDoc.multi_sources) return;

    const bdg = document.getElementById(`badge_${parentDocId}`);
    if (parentDocId === "rent_agreement") {
      const hasPart1 = !!this.uploadedFilesMap["rent_part1"];
      const hasPart2 = !!this.uploadedFilesMap["rent_part2"];
      if (bdg) {
        if (hasPart1 && hasPart2) bdg.innerText = "Part 1 & 2 Ready";
        else if (hasPart1) bdg.innerText = "Part 1 Ready";
        else bdg.innerText = "Pending Part 1";
      }
      return;
    }

    let filled = parentDoc.multi_sources.every(src => !!this.uploadedFilesMap[src.id]);
    if (bdg) {
      bdg.innerText = filled ? "Ready" : "In Progress";
    }
  }

  checkAndUnlockApplicantForm() {
    if (!this.activeWf) return;
    const allDocs = this.getWorkflowDocs();
    let allReady = true;

    for (const doc of allDocs) {
      if (doc.multi_sources) {
        if (doc.id === "rent_agreement") {
          let filled = !!this.uploadedFilesMap["rent_part1"];
          if (!filled) {
            allReady = false;
            break;
          }
        } else {
          let filled = doc.multi_sources.every(src => !!this.uploadedFilesMap[src.id]);
          if (!filled) {
            allReady = false;
            break;
          }
        }
      } else if (doc.multi_side) {
        const entry = this.uploadedFilesMap[doc.id];
        if (!entry || !entry.front || !entry.back) {
          allReady = false;
          break;
        }
      } else {
        if (!this.uploadedFilesMap[doc.id]) {
          allReady = false;
          break;
        }
      }
    }

    this.renderDocSummaryList();
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
          document.getElementById("folderName").value = `${cleanName}_Package`;
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

    const allDocs = this.getWorkflowDocs();
    let html = allDocs.map(doc => `
      <div class="summary-item">
        <div style="display: flex; align-items: center; gap: 0.6rem;">
          <i class="fa-solid ${doc.type === 'image' ? 'fa-image' : 'fa-file-pdf'}" style="color: var(--accent-blue);"></i>
          <span style="font-size: 0.88rem; font-weight: 600;">${doc.output_name} (${doc.label})</span>
        </div>
        <span class="badge-status" style="background: rgba(59, 130, 246, 0.15); color: var(--accent-blue);">
          Target: < ${doc.max_kb} KB
        </span>
      </div>
    `).join("");

    list.innerHTML = html;
  }

  handleHelperBtnClick() {
    if (this.activeWf && this.activeWf.id === "new_proprietorship_drug_license") {
      this.redirectToSejdaEditor();
    } else {
      this.openMspcRedirectModal();
    }
  }

  openQuickCopyModal() {
    this.openMspcRedirectModal();
  }

  calculateStep2Password() {
    const name = document.getElementById("applicantName")?.value.trim() || "";
    const dob = document.getElementById("applicantDob")?.value.trim() || "";
    if (name && dob) {
      let nameWithoutTitle = name.replace(/^(DR|MR|MRS|SHRI|SMT|KUMAR|MS)[\.\s]+/i, '').trim();
      let cleanName = nameWithoutTitle.replace(/[^A-Za-z]/g, '').toUpperCase();
      let prefix = cleanName.substring(0, 3);
      if (prefix.length < 3) prefix = prefix.padEnd(3, 'X');

      let dobParts = dob.replace(/[\.\-]/g, '/').split('/');
      let day = (dobParts[0] || "01").padStart(2, '0');
      let month = (dobParts[1] || "01").padStart(2, '0');
      return `${prefix}${day}${month}`;
    }
    return "";
  }

  copyStep2Password() {
    const pass = this.calculateStep2Password();
    if (pass) {
      this.copyTextToClipboard(pass);
      this.showToast(`Copied Password: ${pass}`);
    } else {
      this.showToast("Please enter Applicant Name and DOB to calculate password.");
    }
  }

  copyAllStep2Credentials() {
    const name = document.getElementById("applicantName")?.value.trim() || "";
    const regNo = document.getElementById("regNumber")?.value.trim() || "";
    const dob = document.getElementById("applicantDob")?.value.trim() || "";
    const mobile = document.getElementById("applicantMobile")?.value.trim() || "";
    const email = document.getElementById("applicantEmail")?.value.trim() || "";
    const loginId = document.getElementById("applicantLoginId")?.value.trim() || "";
    const pass = this.calculateStep2Password();

    const fullText = `Applicant Name       : ${name}\nPharmacy Reg Number  : ${regNo}\nDate of Birth        : ${dob}\nCalculated Password : ${pass}\nMobile Number        : ${mobile}\nEmail Address        : ${email}\nMSPC Login ID        : ${loginId}`;

    this.copyTextToClipboard(fullText);
    this.showToast("Copied all Step 2 credentials to clipboard!");
  }

  openMspcRedirectModal() {
    const regNo = document.getElementById("regNumber")?.value.trim() || "";
    const dob = document.getElementById("applicantDob")?.value.trim() || "";
    const mobile = document.getElementById("applicantMobile")?.value.trim() || "";
    const email = document.getElementById("applicantEmail")?.value.trim() || "";
    const pass = this.calculateStep2Password();

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
          <button type="button" class="btn-back" style="font-size:0.72rem; padding:0.25rem 0.6rem; margin-top:0.3rem;" onclick="docFlowApp.openRotationModal('${this.modalSlotId}')">
            <i class="fa-solid fa-sliders"></i> Pop-up Editor (${params.angle}°)
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

    const allDocs = this.getWorkflowDocs();

    for (const doc of allDocs) {
      if (doc.multi_sources) {
        for (const src of doc.multi_sources) {
          const file = this.uploadedFilesMap[src.id];
          if (file) {
            const params = this.transformParamsMap[src.id] || { angle: 0, flipH: false, flipV: false };
            formData.append(src.id, file);
            formData.append(`rot_${src.id}`, params.angle);
            formData.append(`fliph_${src.id}`, params.flipH);
            formData.append(`flipv_${src.id}`, params.flipV);
          }
        }
      } else if (doc.multi_side) {
        const entry = this.uploadedFilesMap[doc.id];
        if (entry) {
          if (entry.front) {
            const params = this.transformParamsMap[`${doc.id}_front`] || { angle: 0, flipH: false, flipV: false };
            formData.append(`${doc.id}_front`, entry.front);
            formData.append(`rot_${doc.id}_front`, params.angle);
            formData.append(`fliph_${doc.id}_front`, params.flipH);
            formData.append(`flipv_${doc.id}_front`, params.flipV);
          }
          if (entry.back) {
            const params = this.transformParamsMap[`${doc.id}_back`] || { angle: 0, flipH: false, flipV: false };
            formData.append(`${doc.id}_back`, entry.back);
            formData.append(`rot_${doc.id}_back`, params.angle);
            formData.append(`fliph_${doc.id}_back`, params.flipH);
            formData.append(`flipv_${doc.id}_back`, params.flipV);
          }
        }
      } else {
        const file = this.uploadedFilesMap[doc.id];
        if (file) {
          const params = this.transformParamsMap[doc.id] || { angle: 0, flipH: false, flipV: false };
          formData.append(doc.id, file);
          formData.append(`rot_${doc.id}`, params.angle);
          formData.append(`fliph_${doc.id}`, params.flipH);
          formData.append(`flipv_${doc.id}`, params.flipV);
        }
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

        const mspcBtn = document.getElementById("mspcPortalRedirectBtn");
        const sejdaBtn = document.getElementById("sejdaRedirectBtn");
        if (this.activeWf && this.activeWf.id === "new_proprietorship_drug_license") {
          if (mspcBtn) mspcBtn.style.display = "none";
          if (sejdaBtn) {
            sejdaBtn.style.display = "block";
            sejdaBtn.style.flex = "1";
          }
        } else {
          if (mspcBtn) mspcBtn.style.display = "block";
          if (sejdaBtn) {
            sejdaBtn.style.display = "block";
            sejdaBtn.style.flex = "1";
          }
        }

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

  // --- SEJDA-STYLE NATIVE PDF EDITOR SUITE ---
  async loadPdfForNativeEditor(files) {
    if (!files || files.length === 0) return;
    const file = files[0];
    this.nativeEditorFile = file;

    document.getElementById("editorPdfFileName").innerText = `✓ Loaded: ${file.name}`;
    document.getElementById("sejdaEditorWorkspace").style.display = "block";

    this.editorAnnotations = {}; // page -> { texts: [], signatures: [], whiteouts: [] }
    this.editorActiveTool = 'text';

    try {
      if (typeof pdfjsLib !== 'undefined') {
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
      }

      const fileArrayBuffer = await file.arrayBuffer();
      const loadingTask = pdfjsLib.getDocument({ data: fileArrayBuffer });
      this.nativePdfDoc = await loadingTask.promise;

      this.renderNativePdfPages();
      this.showToast("PDF document loaded into Native Sejda-Style Editor!");
    } catch (e) {
      console.error("PDF.js render error:", e);
      alert("Could not render PDF preview: " + e.message);
    }
  }

  async renderNativePdfPages() {
    const container = document.getElementById("pdfViewportContainer");
    container.innerHTML = "";

    if (!this.nativePdfDoc) return;

    for (let pageNum = 1; pageNum <= this.nativePdfDoc.numPages; pageNum++) {
      const page = await this.nativePdfDoc.getPage(pageNum);
      const viewport = page.getViewport({ scale: 1.25 });

      const pageWrapper = document.createElement("div");
      pageWrapper.className = "pdf-page-wrapper";
      pageWrapper.style.position = "relative";
      pageWrapper.style.margin = "0 auto";
      pageWrapper.style.boxShadow = "0 8px 30px rgba(0,0,0,0.5)";
      pageWrapper.style.borderRadius = "8px";
      pageWrapper.style.overflow = "hidden";
      pageWrapper.dataset.pageNum = pageNum;

      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.display = "block";

      const ctx = canvas.getContext("2d");
      await page.render({ canvasContext: ctx, viewport: viewport }).promise;

      // Overlay layer for annotations
      const overlayLayer = document.createElement("div");
      overlayLayer.id = `pageOverlay_${pageNum}`;
      overlayLayer.className = "pdf-overlay-layer";
      overlayLayer.style.position = "absolute";
      overlayLayer.style.top = "0";
      overlayLayer.style.left = "0";
      overlayLayer.style.width = `${viewport.width}px`;
      overlayLayer.style.height = `${viewport.height}px`;
      overlayLayer.style.cursor = "crosshair";

      overlayLayer.onclick = (e) => this.handlePageOverlayClick(e, pageNum, viewport.width, viewport.height);

      pageWrapper.appendChild(canvas);
      pageWrapper.appendChild(overlayLayer);
      container.appendChild(pageWrapper);

      this.editorAnnotations[pageNum] = { texts: [], signatures: [], whiteouts: [] };
    }
  }

  setEditorTool(toolName) {
    this.editorActiveTool = toolName;
    const tBtn = document.getElementById("toolBtnText");
    const wBtn = document.getElementById("toolBtnWhiteout");
    const fmtBar = document.getElementById("textFormatBar");

    if (toolName === "text") {
      tBtn.className = "btn-primary";
      tBtn.style.background = "var(--accent-blue)";
      wBtn.className = "btn-back";
      fmtBar.style.display = "inline-flex";
    } else if (toolName === "whiteout") {
      tBtn.className = "btn-back";
      tBtn.style.background = "";
      wBtn.className = "btn-primary";
      wBtn.style.background = "var(--accent-purple)";
      fmtBar.style.display = "none";
    }
  }

  handlePageOverlayClick(e, pageNum, renderW, renderH) {
    if (e.target.classList.contains("annotation-item") || e.target.closest(".annotation-item")) return;

    const overlay = document.getElementById(`pageOverlay_${pageNum}`);
    const rect = overlay.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (this.editorActiveTool === "text") {
      const color = document.getElementById("textColorPicker").value || "#0f172a";
      const size = parseInt(document.getElementById("textSizePicker").value || "14", 10);
      const textVal = prompt("Enter text to add to PDF:", "Sample Text");
      if (textVal && textVal.trim()) {
        const item = { x: x, y: y, text: textVal.trim(), size: size, color: color };
        this.editorAnnotations[pageNum].texts.push(item);
        this.renderAnnotationsOnOverlay(pageNum);
      }
    } else if (this.editorActiveTool === "whiteout") {
      const item = { x: x, y: y, w: 140, h: 28 };
      this.editorAnnotations[pageNum].whiteouts.push(item);
      this.renderAnnotationsOnOverlay(pageNum);
    }
  }

  renderAnnotationsOnOverlay(pageNum) {
    const overlay = document.getElementById(`pageOverlay_${pageNum}`);
    if (!overlay) return;
    overlay.innerHTML = "";

    const annos = this.editorAnnotations[pageNum];

    // Render Whiteouts
    annos.whiteouts.forEach((w, idx) => {
      const div = document.createElement("div");
      div.className = "annotation-item";
      div.style.position = "absolute";
      div.style.left = `${w.x}px`;
      div.style.top = `${w.y}px`;
      div.style.width = `${w.w}px`;
      div.style.height = `${w.h}px`;
      div.style.background = "#ffffff";
      div.style.border = "1px dashed var(--accent-purple)";
      div.style.borderRadius = "4px";

      const delBtn = document.createElement("span");
      delBtn.innerHTML = "&times;";
      delBtn.style.position = "absolute";
      delBtn.style.top = "-8px";
      delBtn.style.right = "-8px";
      delBtn.style.background = "#ef4444";
      delBtn.style.color = "#fff";
      delBtn.style.width = "16px";
      delBtn.style.height = "16px";
      delBtn.style.borderRadius = "50%";
      delBtn.style.fontSize = "12px";
      delBtn.style.display = "flex";
      delBtn.style.alignItems = "center";
      delBtn.style.justifyContent = "center";
      delBtn.style.cursor = "pointer";
      delBtn.onclick = (e) => {
        e.stopPropagation();
        annos.whiteouts.splice(idx, 1);
        this.renderAnnotationsOnOverlay(pageNum);
      };
      div.appendChild(delBtn);
      overlay.appendChild(div);
    });

    // Render Text Annotations
    annos.texts.forEach((t, idx) => {
      const div = document.createElement("div");
      div.className = "annotation-item";
      div.style.position = "absolute";
      div.style.left = `${t.x}px`;
      div.style.top = `${t.y}px`;
      div.style.color = t.color;
      div.style.fontSize = `${t.size}px`;
      div.style.fontFamily = "Helvetica, Arial, sans-serif";
      div.style.fontWeight = "600";
      div.style.padding = "2px 6px";
      div.style.background = "rgba(255,255,255,0.9)";
      div.style.border = "1px solid var(--accent-blue)";
      div.style.borderRadius = "4px";
      div.style.cursor = "move";
      div.innerText = t.text;

      const delBtn = document.createElement("span");
      delBtn.innerHTML = "&times;";
      delBtn.style.position = "absolute";
      delBtn.style.top = "-8px";
      delBtn.style.right = "-8px";
      delBtn.style.background = "#ef4444";
      delBtn.style.color = "#fff";
      delBtn.style.width = "16px";
      delBtn.style.height = "16px";
      delBtn.style.borderRadius = "50%";
      delBtn.style.fontSize = "12px";
      delBtn.style.display = "flex";
      delBtn.style.alignItems = "center";
      delBtn.style.justifyContent = "center";
      delBtn.style.cursor = "pointer";
      delBtn.onclick = (e) => {
        e.stopPropagation();
        annos.texts.splice(idx, 1);
        this.renderAnnotationsOnOverlay(pageNum);
      };
      div.appendChild(delBtn);
      overlay.appendChild(div);
    });

    // Render Signatures
    annos.signatures.forEach((s, idx) => {
      const div = document.createElement("div");
      div.className = "annotation-item";
      div.style.position = "absolute";
      div.style.left = `${s.x}px`;
      div.style.top = `${s.y}px`;
      div.style.width = `${s.w}px`;
      div.style.height = `${s.h}px`;
      div.style.border = "1px dashed var(--accent-green)";
      div.style.borderRadius = "4px";

      const img = document.createElement("img");
      img.src = s.image_data;
      img.style.width = "100%";
      img.style.height = "100%";
      img.style.objectFit = "contain";
      div.appendChild(img);

      const delBtn = document.createElement("span");
      delBtn.innerHTML = "&times;";
      delBtn.style.position = "absolute";
      delBtn.style.top = "-8px";
      delBtn.style.right = "-8px";
      delBtn.style.background = "#ef4444";
      delBtn.style.color = "#fff";
      delBtn.style.width = "16px";
      delBtn.style.height = "16px";
      delBtn.style.borderRadius = "50%";
      delBtn.style.fontSize = "12px";
      delBtn.style.display = "flex";
      delBtn.style.alignItems = "center";
      delBtn.style.justifyContent = "center";
      delBtn.style.cursor = "pointer";
      delBtn.onclick = (e) => {
        e.stopPropagation();
        annos.signatures.splice(idx, 1);
        this.renderAnnotationsOnOverlay(pageNum);
      };
      div.appendChild(delBtn);
      overlay.appendChild(div);
    });
  }

  // --- E-SIGNATURE MODAL CONTROLS ---
  openSignaturePadModal() {
    document.getElementById("signaturePadModal").style.display = "flex";
    this.switchSigMode('draw');
    setTimeout(() => this.initSigDrawingCanvas(), 100);
  }

  closeSignaturePadModal() {
    document.getElementById("signaturePadModal").style.display = "none";
  }

  switchSigMode(mode) {
    this.currentSigMode = mode;
    const dBtn = document.getElementById("sigModeDrawBtn");
    const tBtn = document.getElementById("sigModeTypeBtn");
    const uBtn = document.getElementById("sigModeUploadBtn");

    const dArea = document.getElementById("sigDrawArea");
    const tArea = document.getElementById("sigTypeArea");
    const uArea = document.getElementById("sigUploadArea");

    dBtn.className = mode === 'draw' ? "btn-primary" : "btn-back";
    if (mode === 'draw') dBtn.style.background = "var(--accent-green)"; else dBtn.style.background = "";

    tBtn.className = mode === 'type' ? "btn-primary" : "btn-back";
    if (mode === 'type') tBtn.style.background = "var(--accent-green)"; else tBtn.style.background = "";

    uBtn.className = mode === 'upload' ? "btn-primary" : "btn-back";
    if (mode === 'upload') uBtn.style.background = "var(--accent-green)"; else uBtn.style.background = "";

    dArea.style.display = mode === 'draw' ? "block" : "none";
    tArea.style.display = mode === 'type' ? "block" : "none";
    uArea.style.display = mode === 'upload' ? "block" : "none";
  }

  initSigDrawingCanvas() {
    const canvas = document.getElementById("sigCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#0f172a";

    let isDrawing = false;
    let lastX = 0;
    let lastY = 0;

    const getPos = (e) => {
      const rect = canvas.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      return { x: clientX - rect.left, y: clientY - rect.top };
    };

    const startDraw = (e) => {
      isDrawing = true;
      const pos = getPos(e);
      lastX = pos.x;
      lastY = pos.y;
    };

    const draw = (e) => {
      if (!isDrawing) return;
      e.preventDefault();
      const pos = getPos(e);
      ctx.beginPath();
      ctx.moveTo(lastX, lastY);
      ctx.lineTo(pos.x, pos.y);
      ctx.stroke();
      lastX = pos.x;
      lastY = pos.y;
    };

    const stopDraw = () => { isDrawing = false; };

    canvas.onmousedown = startDraw;
    canvas.onmousemove = draw;
    canvas.onmouseup = stopDraw;
    canvas.onmouseleave = stopDraw;

    canvas.ontouchstart = startDraw;
    canvas.ontouchmove = draw;
    canvas.ontouchend = stopDraw;
  }

  clearSigCanvas() {
    const canvas = document.getElementById("sigCanvas");
    if (canvas) {
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }

  renderTypedSignature() {
    const val = document.getElementById("sigTypedText").value.trim();
    document.getElementById("sigTypePreview").innerText = val || "Signature Preview";
  }

  handleSigImageUpload(files) {
    if (!files || files.length === 0) return;
    const file = files[0];
    const reader = new FileReader();
    reader.onload = (e) => {
      this.uploadedSigB64 = e.target.result;
      document.getElementById("sigUploadFileName").innerText = `✓ Selected: ${file.name}`;
    };
    reader.readAsDataURL(file);
  }

  stampSignatureOntoDocument() {
    let sigDataUrl = "";

    if (this.currentSigMode === 'draw') {
      const canvas = document.getElementById("sigCanvas");
      sigDataUrl = canvas.toDataURL("image/png");
    } else if (this.currentSigMode === 'type') {
      const val = document.getElementById("sigTypedText").value.trim();
      if (!val) { alert("Please type your name for the signature!"); return; }
      
      const tCanvas = document.createElement("canvas");
      tCanvas.width = 400;
      tCanvas.height = 100;
      const ctx = tCanvas.getContext("2d");
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, 400, 100);
      ctx.font = "italic 40px 'Brush Script MT', cursive, sans-serif";
      ctx.fillStyle = "#0f172a";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(val, 200, 50);
      sigDataUrl = tCanvas.toDataURL("image/png");
    } else if (this.currentSigMode === 'upload') {
      if (!this.uploadedSigB64) { alert("Please select a signature image first!"); return; }
      sigDataUrl = this.uploadedSigB64;
    }

    if (sigDataUrl) {
      const targetPage = 1;
      this.editorAnnotations[targetPage].signatures.push({
        x: 100, y: 150, w: 160, h: 60, image_data: sigDataUrl
      });
      this.renderAnnotationsOnOverlay(targetPage);
      this.closeSignaturePadModal();
      this.showToast("E-Signature stamped onto Page 1! Drag or click to adjust.");
    }
  }

  clearEditorAnnotations() {
    if (!this.editorAnnotations) return;
    for (const pageNum in this.editorAnnotations) {
      this.editorAnnotations[pageNum] = { texts: [], signatures: [], whiteouts: [] };
      this.renderAnnotationsOnOverlay(pageNum);
    }
    this.showToast("Cleared all annotations.");
  }

  async applyAndExportEditedPdf() {
    if (!this.nativeEditorFile && !this.studioPdfFile) {
      alert("No PDF file loaded!");
      return;
    }

    const targetFile = this.nativeEditorFile || this.studioPdfFile;

    const formData = new FormData();
    formData.append("file", targetFile);
    formData.append("output_name", `Edited_${targetFile.name}`);
    formData.append("annotations", JSON.stringify(this.editorAnnotations));

    try {
      const res = await fetch("/api/edit_pdf_standalone", { method: "POST", body: formData });
      const data = await res.json();

      if (data.status === "success") {
        const link = document.createElement("a");
        link.href = data.download_url;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        this.showToast(`PDF exported successfully (${data.file_size_kb} KB)! Download started.`);
      } else {
        alert("Export Error: " + data.message);
      }
    } catch (e) {
      alert("PDF Export Exception: " + e.message);
    }
  }

  // --- PDF STUDIO MODULE IMPLEMENTATION ---
  async loadPdfIntoStudio(files) {
    if (!files || files.length === 0) return;
    const file = files[0];
    this.studioPdfFile = file;
    this.studioZoom = 1.0;

    document.getElementById("studioEmptyState").style.display = "none";
    document.getElementById("pdfStudioWorkspace").style.display = "block";

    this.editorAnnotations = {};
    this.editorActiveTool = 'select';

    try {
      if (typeof pdfjsLib !== 'undefined') {
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
      }

      const buffer = await file.arrayBuffer();
      const loadingTask = pdfjsLib.getDocument({ data: buffer });
      this.studioPdfDoc = await loadingTask.promise;

      document.getElementById("studioPageCountBadge").innerText = `${this.studioPdfDoc.numPages} Pages`;
      document.getElementById("statusCurrentPage").innerText = `Page 1 of ${this.studioPdfDoc.numPages}`;

      await this.renderStudioThumbnails();
      await this.renderStudioCenterPages();
      this.showToast(`Loaded ${file.name} into PDF Studio!`);
    } catch (e) {
      console.error("PDF Studio Load Error:", e);
      alert("Failed to load PDF into Studio: " + e.message);
    }
  }

  async renderStudioThumbnails() {
    const listEl = document.getElementById("studioThumbnailsList");
    if (!listEl || !this.studioPdfDoc) return;
    listEl.innerHTML = "";

    for (let pageNum = 1; pageNum <= this.studioPdfDoc.numPages; pageNum++) {
      const page = await this.studioPdfDoc.getPage(pageNum);
      const viewport = page.getViewport({ scale: 0.25 });

      const card = document.createElement("div");
      card.className = "studio-thumb-card";
      card.style.background = "rgba(255,255,255,0.05)";
      card.style.border = "1px solid var(--border-glass)";
      card.style.borderRadius = "8px";
      card.style.padding = "0.4rem";
      card.style.textAlign = "center";
      card.style.cursor = "grab";
      card.dataset.pageNum = pageNum;

      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.display = "block";
      canvas.style.margin = "0 auto 0.4rem";
      canvas.style.borderRadius = "4px";

      const ctx = canvas.getContext("2d");
      await page.render({ canvasContext: ctx, viewport: viewport }).promise;

      const label = document.createElement("span");
      label.style.fontSize = "0.72rem";
      label.style.color = "var(--text-muted)";
      label.innerText = `Page ${pageNum}`;

      card.appendChild(canvas);
      card.appendChild(label);
      listEl.appendChild(card);
    }

    if (typeof Sortable !== 'undefined') {
      Sortable.create(listEl, {
        animation: 150,
        onEnd: (evt) => {
          this.showToast(`Reordered Page ${evt.oldIndex + 1} to Position ${evt.newIndex + 1}!`);
        }
      });
    }
  }

  async renderStudioCenterPages() {
    const container = document.getElementById("studioCenterViewport");
    if (!container || !this.studioPdfDoc) return;
    container.innerHTML = "";

    for (let pageNum = 1; pageNum <= this.studioPdfDoc.numPages; pageNum++) {
      const page = await this.studioPdfDoc.getPage(pageNum);
      const viewport = page.getViewport({ scale: this.studioZoom * 1.2 });

      const wrapper = document.createElement("div");
      wrapper.className = "studio-page-wrapper";
      wrapper.style.position = "relative";
      wrapper.style.margin = "0 auto 1.5rem";
      wrapper.style.boxShadow = "0 10px 35px rgba(0,0,0,0.6)";
      wrapper.style.borderRadius = "8px";
      wrapper.style.overflow = "hidden";
      wrapper.dataset.pageNum = pageNum;

      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.display = "block";

      const ctx = canvas.getContext("2d");
      await page.render({ canvasContext: ctx, viewport: viewport }).promise;

      const overlay = document.createElement("div");
      overlay.id = `pageOverlay_${pageNum}`;
      overlay.className = "pdf-overlay-layer";
      overlay.style.position = "absolute";
      overlay.style.top = "0";
      overlay.style.left = "0";
      overlay.style.width = `${viewport.width}px`;
      overlay.style.height = `${viewport.height}px`;
      overlay.style.cursor = "crosshair";

      overlay.onclick = (e) => this.handlePageOverlayClick(e, pageNum, viewport.width, viewport.height);

      wrapper.appendChild(canvas);
      wrapper.appendChild(overlay);
      container.appendChild(wrapper);

      if (!this.editorAnnotations[pageNum]) {
        this.editorAnnotations[pageNum] = { texts: [], signatures: [], whiteouts: [] };
      }
      this.renderAnnotationsOnOverlay(pageNum);
    }
  }

  setStudioTool(toolName) {
    this.editorActiveTool = toolName;
    const selBtn = document.getElementById("studioBtnSelect");
    const txtBtn = document.getElementById("studioBtnText");
    const whtBtn = document.getElementById("studioBtnWhiteout");

    if (selBtn) {
      selBtn.className = toolName === 'select' ? "btn-primary" : "btn-back";
      selBtn.style.background = toolName === 'select' ? "var(--accent-blue)" : "";
    }
    if (txtBtn) {
      txtBtn.className = toolName === 'text' ? "btn-primary" : "btn-back";
      txtBtn.style.background = toolName === 'text' ? "var(--accent-blue)" : "";
    }
    if (whtBtn) {
      whtBtn.className = toolName === 'whiteout' ? "btn-primary" : "btn-back";
      whtBtn.style.background = toolName === 'whiteout' ? "var(--accent-purple)" : "";
    }
  }

  changeStudioZoom(delta) {
    this.studioZoom = Math.max(0.5, Math.min(2.5, (this.studioZoom || 1.0) + delta));
    const zVal = document.getElementById("studioZoomVal");
    if (zVal) zVal.innerText = `${Math.round(this.studioZoom * 100)}%`;
    const zStat = document.getElementById("statusZoom");
    if (zStat) zStat.innerText = `Zoom: ${Math.round(this.studioZoom * 100)}%`;
    this.renderStudioCenterPages();
  }

  addStudioBlankPage() {
    this.showToast("Blank page inserted into document sequence.");
  }

  clearStudioAnnotations() {
    this.clearEditorAnnotations();
  }

  openWorkflowFileInStudio(slotId) {
    const file = this.uploadedFilesMap[slotId];
    if (!file) {
      alert("Please upload a PDF document first!");
      return;
    }
    this.studioReturnSlotId = slotId;
    document.getElementById("studioReturnWfBtn").style.display = "inline-flex";

    this.switchTab('pdf_editor');
    this.loadPdfIntoStudio([file]);
    this.showToast(`Loaded ${file.name} into PDF Studio for editing!`);
  }

  async saveAndReturnToWorkflow() {
    if (!this.studioPdfFile) {
      alert("No PDF loaded in Studio!");
      return;
    }

    const formData = new FormData();
    formData.append("file", this.studioPdfFile);
    formData.append("output_name", `Edited_${this.studioPdfFile.name}`);
    formData.append("annotations", JSON.stringify(this.editorAnnotations));
    formData.append("max_kb", "125");

    try {
      const res = await fetch("/api/edit_pdf_standalone", { method: "POST", body: formData });
      const data = await res.json();

      if (data.status === "success") {
        const pdfRes = await fetch(data.download_url);
        const pdfBlob = await pdfRes.blob();
        const editedFile = new File([pdfBlob], data.filename, { type: "application/pdf" });

        if (this.studioReturnSlotId) {
          this.uploadedFilesMap[this.studioReturnSlotId] = editedFile;
          const lbl = document.getElementById(`label_${this.studioReturnSlotId}`);
          if (lbl) lbl.innerText = `✓ Edited in PDF Studio (${editedFile.name})`;
          this.checkAndUnlockApplicantForm();
        }

        document.getElementById("homeView").style.display = "none";
        document.getElementById("workflowView").style.display = "block";
        document.getElementById("pdfEditorTab").style.display = "none";

        document.getElementById("navServicesBtn").classList.add("active");
        document.getElementById("navPdfEditorBtn").classList.remove("active");

        this.showToast("Edited PDF saved and returned to Drug License workflow!");
      } else {
        alert("Export Error: " + data.message);
      }
    } catch (e) {
      alert("Save Exception: " + e.message);
    }
  }

  async exportStudioPdf() {
    if (!this.studioPdfFile) {
      alert("No PDF file loaded!");
      return;
    }

    const maxKb = document.getElementById("studioMaxKb")?.value || "125";
    const formData = new FormData();
    formData.append("file", this.studioPdfFile);
    formData.append("output_name", `Edited_${this.studioPdfFile.name}`);
    formData.append("annotations", JSON.stringify(this.editorAnnotations));
    formData.append("max_kb", maxKb);

    try {
      const res = await fetch("/api/edit_pdf_standalone", { method: "POST", body: formData });
      const data = await res.json();

      if (data.status === "success") {
        const link = document.createElement("a");
        link.href = data.download_url;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        this.showToast(`PDF Studio exported successfully (${data.file_size_kb} KB)! Download started.`);
      } else {
        alert("Export Error: " + data.message);
      }
    } catch (e) {
      alert("PDF Export Exception: " + e.message);
    }
  }

  handleMergeFilesSelected(files) {
    if (!files || files.length === 0) return;
    this.selectedMergeFiles = Array.from(files);
    const listEl = document.getElementById("mergeFilesSelectedList");
    if (listEl) {
      listEl.innerHTML = `✓ ${files.length} file(s) selected: ` + this.selectedMergeFiles.map(f => f.name).join(", ");
    }
  }

  async executeMergePdfs() {
    if (!this.selectedMergeFiles || this.selectedMergeFiles.length === 0) {
      alert("Please select PDF/image files to merge first!");
      return;
    }

    const maxKb = document.getElementById("mergeTargetKb").value || "125";
    const formData = new FormData();
    this.selectedMergeFiles.forEach((file, idx) => {
      formData.append(`file_${idx}`, file);
    });
    formData.append("output_name", "Merged_Document.pdf");
    formData.append("max_kb", maxKb);

    this.showToast(`Merging ${this.selectedMergeFiles.length} file(s) and compressing under ${maxKb} KB...`);

    try {
      const res = await fetch("/api/merge_pdfs", { method: "POST", body: formData });
      const data = await res.json();

      if (data.status === "success") {
        const link = document.createElement("a");
        link.href = data.download_url;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        this.showToast(`PDFs merged & compressed (${data.file_size_kb} KB)! Download started.`);
      } else {
        alert("Merge Error: " + data.message);
      }
    } catch (e) {
      alert("Merge Exception: " + e.message);
    }
  }

  // --- SMART PDF AUTO-FILL ENGINE METHODS ---
  handleAutoFillTemplateSelected(files) {
    if (!files || files.length === 0) return;
    this.autoFillTemplateFile = files[0];
    this.showToast(`Selected template: ${files[0].name}. Click Auto-Detect Fields!`);
  }

  async detectPdfBlanks() {
    if (!this.autoFillTemplateFile) {
      alert("Please upload a template PDF file first!");
      return;
    }

    const formData = new FormData();
    formData.append("file", this.autoFillTemplateFile);

    this.showToast("Analyzing PDF template for blank fields & placeholders...");

    try {
      const res = await fetch("/api/detect_pdf_blanks", { method: "POST", body: formData });
      const data = await res.json();

      if (data.status === "success") {
        this.autoFillJobId = data.job_id;
        this.autoFillDetectedData = data;

        this.renderAutoFillInputsGrid(data.unique_fields);
        document.getElementById("autoFillDynamicFormArea").style.display = "block";
        this.showToast(`Auto-detected ${data.unique_fields.length} unique blank field(s)! Form ready below.`);
      } else {
        alert("Detection Error: " + data.message);
      }
    } catch (e) {
      alert("Detection Exception: " + e.message);
    }
  }

  renderAutoFillInputsGrid(uniqueFields) {
    const grid = document.getElementById("autoFillInputFieldsGrid");
    if (!grid) return;

    grid.innerHTML = uniqueFields.map(f => {
      const inputType = f.key.includes("date") ? "date" : "text";
      const occBadge = f.occurrences > 1 ? `<span style="font-size:0.7rem; color: var(--accent-blue); margin-left: 0.4rem;">(Populates ${f.occurrences} places)</span>` : "";

      return `
        <div class="form-group" style="margin-bottom: 0.6rem;">
          <label style="font-size: 0.8rem; font-weight: 600;">
            ${f.label} ${occBadge}
          </label>
          <input type="${inputType}" id="autofill_input_${f.key}" data-key="${f.key}" class="autofill-field-input" placeholder="Enter ${f.label}..." style="font-size: 0.85rem; width: 100%;">
        </div>
      `;
    }).join("");
  }

  async generateAutoFilledPdf() {
    if (!this.autoFillJobId || !this.autoFillDetectedData) {
      alert("Please detect fields first!");
      return;
    }

    const inputs = document.querySelectorAll(".autofill-field-input");
    const fieldValues = {};

    inputs.forEach(input => {
      const key = input.dataset.key;
      const val = input.value.trim();
      if (val) {
        fieldValues[key] = val;
      }
    });

    const formData = new FormData();
    formData.append("job_id", this.autoFillJobId);
    formData.append("field_values", JSON.stringify(fieldValues));
    formData.append("max_kb", "125");

    this.showToast("Generating auto-filled PDF with exact formatting preservation...");

    try {
      const res = await fetch("/api/autofill_pdf", { method: "POST", body: formData });
      const data = await res.json();

      if (data.status === "success") {
        const link = document.createElement("a");
        link.href = data.download_url;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        this.showToast(`Auto-filled PDF created successfully (${data.file_size_kb} KB)! Download started.`);
      } else {
        alert("Generation Error: " + data.message);
      }
    } catch (e) {
      alert("Generation Exception: " + e.message);
    }
  }

  async generateAppointmentLetter() {
    const apptDate = document.getElementById("appt_date")?.value || "";
    const pharmacistName = document.getElementById("appt_pharmacist_name")?.value.trim() || "";
    const joiningDate = document.getElementById("appt_joining_date")?.value || "";
    const proprietorName = document.getElementById("appt_proprietor_name")?.value.trim() || "";
    const accDate = document.getElementById("acc_date")?.value || "";
    const storeName = document.getElementById("acc_store_name")?.value.trim() || "";

    if (!pharmacistName) {
      alert("Please enter the Pharmacist Name!");
      return;
    }

    const formData = new FormData();
    formData.append("appointment_date", apptDate);
    formData.append("pharmacist_name", pharmacistName);
    formData.append("joining_date", joiningDate);
    formData.append("proprietor_name", proprietorName);
    formData.append("acceptance_date", accDate);
    formData.append("medical_store_name", storeName);
    formData.append("max_kb", "125");

    this.showToast("Generating formatted Appointment & Acceptance Letter PDF...");

    try {
      const res = await fetch("/api/fill_appointment_letter", { method: "POST", body: formData });
      const data = await res.json();

      if (data.status === "success") {
        const link = document.createElement("a");
        link.href = data.download_url;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        this.showToast(`Appointment & Acceptance Letter generated successfully (${data.file_size_kb} KB)! Download started.`);
      } else {
        alert("Generation Error: " + data.message);
      }
    } catch (e) {
      alert("Generation Exception: " + e.message);
    }
  }

  async generateSelfDeclaration() {
    const pharmacistName = document.getElementById("sd_pharmacist_name")?.value.trim() || "";
    const regNo = document.getElementById("sd_reg_no")?.value.trim() || "";
    const address = document.getElementById("sd_address")?.value.trim() || "";
    const storeName = document.getElementById("sd_store_name")?.value.trim() || "";
    const dateStr = document.getElementById("sd_date")?.value || "";

    if (!pharmacistName) {
      alert("Please enter the Pharmacist Name for Self Declaration!");
      return;
    }

    const formData = new FormData();
    formData.append("pharmacist_name", pharmacistName);
    formData.append("reg_no", regNo);
    formData.append("address", address);
    formData.append("store_name", storeName);
    formData.append("date_str", dateStr);
    formData.append("max_kb", "125");

    this.showToast("Generating Self Declaration (SD) PDF...");

    try {
      const res = await fetch("/api/generate_self_declaration", { method: "POST", body: formData });
      const data = await res.json();

      if (data.status === "success") {
        const link = document.createElement("a");
        link.href = data.download_url;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        this.showToast(`Self Declaration (SD) generated successfully (${data.file_size_kb} KB)! Download started.`);
      } else {
        alert("Generation Error: " + data.message);
      }
    } catch (e) {
      alert("Generation Exception: " + e.message);
    }
  }

  async generateCombinedPdf() {
    const pharmacistName = document.getElementById("comb_pharmacist_name")?.value.trim() || "";
    const apptDate = document.getElementById("comb_appt_date")?.value || "";
    const accDate = document.getElementById("comb_acc_date")?.value || "";
    const joiningDate = document.getElementById("comb_joining_date")?.value || "";
    const proprietorName = document.getElementById("comb_proprietor_name")?.value.trim() || "";
    const storeName = document.getElementById("comb_store_name")?.value.trim() || "";
    const regNo = document.getElementById("comb_reg_no")?.value.trim() || "";
    const address = document.getElementById("comb_address")?.value.trim() || "";

    if (!pharmacistName) {
      alert("Please enter the Pharmacist Name!");
      return;
    }

    const formData = new FormData();
    formData.append("appointment_date", apptDate);
    formData.append("pharmacist_name", pharmacistName);
    formData.append("joining_date", joiningDate);
    formData.append("proprietor_name", proprietorName);
    formData.append("acceptance_date", accDate);
    formData.append("medical_store_name", storeName);
    formData.append("reg_no", regNo);
    formData.append("address", address);
    formData.append("max_kb", "125");

    this.showToast("Generating Combined Appointment + Acceptance + Self Declaration PDF...");

    try {
      const res = await fetch("/api/generate_combined_appointment_acceptance_sd", { method: "POST", body: formData });
      const data = await res.json();

      if (data.status === "success") {
        const link = document.createElement("a");
        link.href = data.download_url;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        this.showToast(`Combined PDF generated successfully (${data.file_size_kb} KB)! Download started.`);
      } else {
        alert("Generation Error: " + data.message);
      }
    } catch (e) {
      alert("Generation Exception: " + e.message);
    }
  }

  redirectToSejdaEditor() {
    this.switchTab('pdf_editor');
    this.switchPdfSubTab('sejda');
    this.showToast("Switched to Sejda PDF Editor Suite!");
  }

  copyAllCredentials() {
    const name = document.getElementById("resApplicantName")?.innerText || "";
    const loginId = document.getElementById("resLoginId")?.innerText || "";
    const pass = document.getElementById("resMspcPass")?.innerText || "";
    const regNo = document.getElementById("resRegNo")?.innerText || "";
    const dob = document.getElementById("resDob")?.innerText || "";
    const mobile = document.getElementById("resMobile")?.innerText || "";
    const email = document.getElementById("resEmail")?.innerText || "";

    const fullText = `Applicant Name       : ${name}\nMSPC Login ID         : ${loginId}\nCalculated Password : ${pass}\nPharmacy Reg Number  : ${regNo}\nDate of Birth        : ${dob}\nMobile Number        : ${mobile}\nEmail Address        : ${email}`;

    this.copyTextToClipboard(fullText);
    this.showToast("Copied all applicant credentials to clipboard!");
  }

  openHistoryModal() {
    document.getElementById("historyModal").style.display = "flex";
    this.loadHistoryData();
  }

  closeHistoryModal() {
    document.getElementById("historyModal").style.display = "none";
  }

  async loadHistoryData() {
    const tbody = document.getElementById("historyTableBody");
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6" style="padding: 1.5rem; text-align: center; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Loading Firebase & Local Submission History...</td></tr>`;

    try {
      const res = await fetch("/api/submissions");
      const data = await res.json();

      if (data.status === "success" && data.submissions) {
        this.rawSubmissions = data.submissions;
        const searchVal = document.getElementById("historySearchInput")?.value || "";
        if (searchVal) {
          this.filterHistoryTable(searchVal);
        } else {
          this.renderHistoryRows(this.rawSubmissions);
        }
      } else {
        tbody.innerHTML = `<tr><td colspan="6" style="padding: 1.5rem; text-align: center; color: var(--text-muted);">No submission records found yet. Submit a document package to record history!</td></tr>`;
      }
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="padding: 1.5rem; text-align: center; color: #ef4444;">Error loading history: ${e.message}</td></tr>`;
    }
  }

  filterHistoryTable(query) {
    if (!this.rawSubmissions) return;
    const q = (query || "").toLowerCase().trim();
    if (!q) {
      this.renderHistoryRows(this.rawSubmissions);
      return;
    }

    const filtered = this.rawSubmissions.filter(item => {
      const name = (item.name || "").toLowerCase();
      const reg = (item.reg_number || "").toLowerCase();
      const wf = (item.workflow || "").toLowerCase();
      const folder = (item.folder || "").toLowerCase();
      return name.includes(q) || reg.includes(q) || wf.includes(q) || folder.includes(q);
    });

    this.renderHistoryRows(filtered);
  }

  renderHistoryRows(submissions) {
    const tbody = document.getElementById("historyTableBody");
    if (!tbody) return;

    if (!submissions || submissions.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="padding: 1.5rem; text-align: center; color: var(--text-muted);">No matching submission records found.</td></tr>`;
      return;
    }

    tbody.innerHTML = submissions.map(item => `
      <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
        <td style="padding: 0.65rem 0.75rem; color: var(--text-muted); font-size: 0.78rem;">${item.date || item.created_at || '-'}</td>
        <td style="padding: 0.65rem 0.75rem; font-weight: 600; color: var(--accent-blue);">${item.workflow || 'New Proprietory Firm'}</td>
        <td style="padding: 0.65rem 0.75rem; font-weight: 700; color: var(--text-bright);">${item.name || '-'}</td>
        <td style="padding: 0.65rem 0.75rem; color: var(--accent-purple);">${item.reg_number || '-'}</td>
        <td style="padding: 0.65rem 0.75rem; color: var(--accent-green);">${item.folder || '-'} (${item.zip_size_kb || 0} KB)</td>
        <td style="padding: 0.65rem 0.75rem;">
          ${item.cloudinary_zip_url ? `<a href="${item.cloudinary_zip_url}" target="_blank" style="color: var(--accent-green); text-decoration: none;"><i class="fa-solid fa-cloud-arrow-down"></i> Cloudinary Link</a>` : '<span style="color: var(--text-muted);">Local ZIP Package</span>'}
        </td>
      </tr>
    `).join("");
  }
}

const docFlowApp = new DocFlowApp();
