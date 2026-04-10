const sourceCode = document.getElementById("sourceCode");
const targetCode = document.getElementById("targetCode");
const statusBox = document.getElementById("statusBox");
const generateBtn = document.getElementById("generateBtn");
const copyBtn = document.getElementById("copyBtn");

const SAMPLE_PY = `class Counter:
    def __init__(self, start):
        self.value = start

    def bump(self, steps):
        total = self.value
        for i in range(0, steps, 1):
            total = total + 1
        self.value = total
        return self.value

c = Counter(2)
print(c.bump(3))
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
