#!/bin/bash
# Check Montreal Forced Aligner setup

set -e

echo "🔍 Checking Montreal Forced Aligner setup..."
echo ""

# Check conda
if ! command -v conda &> /dev/null; then
    echo "❌ conda not found in PATH"
    echo "   Install from: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi
echo "✅ conda found: $(which conda)"

# Get conda base from conda itself
CONDA_BASE=${CONDA_BASE:-$(conda info --base)}
echo "📁 Conda base: $CONDA_BASE"

# Check if aligner environment exists
MFA_ENV=${MFA_ENV:-aligner}
if conda env list | grep -q "^${MFA_ENV} "; then
    echo "✅ Conda environment '$MFA_ENV' exists"
else
    echo "❌ Conda environment '$MFA_ENV' not found"
    echo "   Create it with: conda create -n aligner -c conda-forge montreal-forced-aligner"
    exit 1
fi

# Activate environment and check MFA
source ${CONDA_BASE}/etc/profile.d/conda.sh
conda activate ${MFA_ENV}

if ! command -v mfa &> /dev/null; then
    echo "❌ mfa command not found in '$MFA_ENV' environment"
    echo "   Install with: conda install -c conda-forge montreal-forced-aligner"
    exit 1
fi
echo "✅ mfa found: $(which mfa)"
echo "   Version: $(mfa version)"

# Check for models
echo ""
echo "📦 Checking for required models..."

if mfa model list acoustic | grep -q "english_us_arpa"; then
    echo "✅ Acoustic model 'english_us_arpa' installed"
else
    echo "❌ Acoustic model 'english_us_arpa' not found"
    echo "   Download with: mfa model download acoustic english_us_arpa"
fi

if mfa model list dictionary | grep -q "english_us_arpa"; then
    echo "✅ Dictionary 'english_us_arpa' installed"
else
    echo "❌ Dictionary 'english_us_arpa' not found"
    echo "   Download with: mfa model download dictionary english_us_arpa"
fi

echo ""
echo "✨ MFA setup check complete!"

