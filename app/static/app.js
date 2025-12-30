let currentJobId = null;

const form = document.getElementById("generate-form");
const resultDiv = document.getElementById("result");
const scoreSpan = document.getElementById("score");
const summarySpan = document.getElementById("summary");
const resumeSourceSpan = document.getElementById("resume-source");
const versionSpan = document.getElementById("version");
const versionsList = document.getElementById("versions-list");
const downloadLink = document.getElementById("download-link");
const redoBtn = document.getElementById("redo-btn");
const newResumePre = document.getElementById("new-resume-text");
const diffView = document.getElementById("diff-view");
const pasteBlock = document.getElementById("paste-block");
const uploadBlock = document.getElementById("upload-block");
const resumeTextarea = document.getElementById("resume");
const resumeDocxInput = document.getElementById("resume-docx");
const loader = document.getElementById("loader");
const loaderText = document.getElementById("loader-text");
const generateBtn = document.getElementById("generate-btn");

function getResumeMode() {
  return document.querySelector('input[name="resume_mode"]:checked').value;
}

document.querySelectorAll('input[name="resume_mode"]').forEach((el) => {
  el.addEventListener("change", () => {
    const mode = getResumeMode();
    if (mode === "paste") {
      pasteBlock.style.display = "block";
      uploadBlock.style.display = "none";
    } else {
      pasteBlock.style.display = "none";
      uploadBlock.style.display = "block";
    }
  });
});

function updateResult(data) {
  console.log("Update result:", data);
  scoreSpan.textContent = data.score;
  summarySpan.textContent = data.summary;
  versionSpan.textContent = data.version;
  resumeSourceSpan.textContent = data.resume_source || "";
  downloadLink.href = data.download_url;
  downloadLink.textContent = `Download ${data.docx_file}`;

  versionsList.innerHTML = "";
  if (Array.isArray(data.all_versions)) {
    for (const filename of data.all_versions) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `/download/${filename}`;
      a.textContent = filename;
      a.target = "_blank";
      li.appendChild(a);
      versionsList.appendChild(li);
    }
  }

  newResumePre.textContent = data.new_resume_text || "";
  diffView.innerHTML = data.diff_html || "";

  resultDiv.style.display = "block";
}

function setLoading(isLoading, message = "Working...") {
  if (generateBtn) {
    generateBtn.disabled = isLoading;
  }
  if (redoBtn) {
    redoBtn.disabled = isLoading;
  }
  if (loader) {
    loader.style.display = isLoading ? "block" : "none";
    if (isLoading && loaderText) {
      loaderText.textContent = message;
    }
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const jd = document.getElementById("jd").value;
  const company = document.getElementById("company").value;
  const mode = getResumeMode();

  const formData = new FormData();
  formData.append("jd", jd);
  formData.append("company", company);
  formData.append("resume_mode", mode);

  if (mode === "paste") {
    const resumeText = resumeTextarea.value.trim();
    formData.append("base_resume", resumeText);
  } else {
    const file = resumeDocxInput.files[0];
    if (file) {
      formData.append("resume_file", file);
    }
  }

  try {
    setLoading(true, "Generating resume...");
    const resp = await fetch("/generate", {
      method: "POST",
      body: formData,
    });

    if (!resp.ok) {
      const errorText = await resp.text();
      alert(`Failed to generate resume: ${errorText}`);
      return;
    }

    const data = await resp.json();
    currentJobId = data.job_id;
    updateResult(data);
  } catch (err) {
    console.error(err);
    alert("An unexpected error occurred while generating the resume.");
  } finally {
    setLoading(false);
  }
});

redoBtn.addEventListener("click", async () => {
  if (!currentJobId) return;

  try {
    setLoading(true, "Regenerating resume...");
    const resp = await fetch(`/regenerate/${currentJobId}`, {
      method: "POST",
    });

    if (!resp.ok) {
      const errorText = await resp.text();
      alert(`Failed to regenerate resume: ${errorText}`);
      return;
    }

    const data = await resp.json();
    updateResult(data);
  } catch (err) {
    console.error(err);
    alert("An unexpected error occurred while regenerating the resume.");
  } finally {
    setLoading(false);
  }
});
