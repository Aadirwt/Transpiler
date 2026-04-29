const sourceCode = document.getElementById("sourceCode");
const targetCode = document.getElementById("targetCode");
const statusBox = document.getElementById("statusBox");
const generateBtn = document.getElementById("generateBtn");
const copyBtn = document.getElementById("copyBtn");

const SAMPLE_PY = `n = 5  # Number of rows
num = 1
for i in range(1, n + 1):
    for j in range(1, i + 1):
        print(num, end=' ')
        num += 1
    print()   
`;

function setStatus(message, isError = false) {
    statusBox.textContent = message;
    statusBox.classList.toggle("error", isError);
}

async function handleGenerate() {
    const payload = {
        source_code: sourceCode.value,
    };

    setStatus("Generating target code...");
    generateBtn.disabled = true;

    try {
        const response = await fetch("/api/transpile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
            targetCode.value = "";
            setStatus(data.error || "Transpilation failed.", true);
            return;
        }

        targetCode.value = data.target_code || "";
        const status = data.semantic_match ? "Semantic check passed." : "Generated with warnings.";
        setStatus(status);
    } catch (err) {
        targetCode.value = "";
        setStatus(`Request failed: ${err}`, true);
    } finally {
        generateBtn.disabled = false;
    }
}

async function handleCopy() {
    if (!targetCode.value) {
        setStatus("No target code available to copy.", true);
        return;
    }
    try {
        await navigator.clipboard.writeText(targetCode.value);
        setStatus("Target code copied.");
    } catch {
        setStatus("Copy failed. Clipboard permission may be blocked.", true);
    }
}

generateBtn.addEventListener("click", handleGenerate);
copyBtn.addEventListener("click", handleCopy);

sourceCode.value = SAMPLE_PY;
setStatus("Ready. Write Python code and generate Java.");
