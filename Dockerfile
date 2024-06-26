FROM ubuntu:24.04

# Set args
ARG GITHUB_ACTIONS_USER_NAME="runner"
ARG GITHUB_ACTIONS_USER_ID="1001"
ARG GITHUB_ACTIONS_GROUP_NAME="docker"
ARG GITHUB_ACTIONS_GROUP_ID="121"
ARG CONDA_ENV_NAME="cwl-ica"
ARG YQ_VERSION="v4.35.2"
ARG ICAV2_CLI_VERSION="2.26.0"
ARG ICAV2_PLUGINS_CLI_VERSION="v2.27.0.dev20240626152843"
ARG ICAV2_PLUGINS_CLI_CONDA_PYTHON_VERSION="3.12"
ARG ICAV2_PLUGINS_CLI_CONDA_ENV_NAME="python3.12"
ARG CWL_UTILS_REPO_PATH="https://github.com/alexiswl/cwl-utils"
ARG CWL_UTILS_REPO_BRANCH="enhancement/cwl-inputs-schema-gen"

ARG MINIFORGE_NAME="Miniforge3"
ARG MINIFORGE_VERSION="24.3.0-0"
ARG TARGETPLATFORM="linux/amd64"

ENV CONDA_DIR=/opt/conda

RUN export DEBIAN_FRONTEND=noninteractive && \
    ( \
      echo "Updating Apt" 1>&2 && \
      apt update -y -q && \
      echo "Installing jq, nodejs, rsync, graphviz and parallel" 1>&2 && \
      apt install -y -q \
        jq \
        nodejs \
        rsync \
        graphviz \
        parallel \
        gcc \
        python3-dev \
        curl \
        build-essential \
        automake \
        autoconf \
        libtool \
        unzip \
        nghttp2 \
        libnghttp2-dev \
        libssl-dev \
        wget \
        autoconf \
        busybox \
        bzip2 \
        ca-certificates \
        git \
        tini &&  \
      echo "Cleaning up after apt installations" 1>&2 && \
      apt clean -y -q \
    ) && \
    ( \
      echo "Installing conda" 1>&2 && \
      CONDA_TARGETPLATFORM_NAME="$(echo "${TARGETPLATFORM#linux/}" | sed 's/amd64/x86_64/g')" && \
      echo "https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_VERSION}/${MINIFORGE_NAME}-${MINIFORGE_VERSION}-Linux-${CONDA_TARGETPLATFORM_NAME}.sh" && \
      wget --no-hsts --quiet \
        --output-document /tmp/miniforge.sh \
        "https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_VERSION}/${MINIFORGE_NAME}-${MINIFORGE_VERSION}-Linux-${CONDA_TARGETPLATFORM_NAME}.sh" && \
      /bin/bash /tmp/miniforge.sh -b -p ${CONDA_DIR} && \
      rm /tmp/miniforge.sh && \
      echo "Updating conda" 1>&2 && \
      "${CONDA_DIR}/bin/conda" update --yes \
        --name base \
        --channel conda-forge \
        --channel defaults \
        conda && \
      "${CONDA_DIR}/bin/conda" clean --tarballs --index-cache --packages --yes && \
      find ${CONDA_DIR} -follow -type f -name '*.a' -delete && \
      find ${CONDA_DIR} -follow -type f -name '*.pyc' -delete && \
      "${CONDA_DIR}/bin/conda" clean --force-pkgs-dirs --all --yes  && \
      echo ". ${CONDA_DIR}/etc/profile.d/conda.sh && conda activate base" >> /etc/skel/.bashrc && \
      echo ". ${CONDA_DIR}/etc/profile.d/conda.sh && conda activate base" >> ~/.bashrc \
    ) && \
    ( \
      echo "Installing yq" 1>&2 && \
      wget --quiet \
        --output-document /usr/bin/yq \
        "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64" && \
      chmod +x /usr/bin/yq \
    ) && \
    ( \
      echo "Installing gh binary" && \
      curl --fail --silent --show-error --location \
        "https://cli.github.com/packages/githubcli-archive-keyring.gpg" | \
      dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
      chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | \
      tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \
      apt update -y -q && \
      apt install gh -y -q && \
      apt clean -y -q \
    ) && \
    ( \
      echo "Installing aws cli" 1>&2 && \
      wget --quiet "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" \
        --output-document "awscliv2.zip" && \
      unzip -qq awscliv2.zip && \
      ./aws/install && \
      rm -rf aws/ awscliv2.zip \
    ) && \
    ( \
      echo "Installing ICAv2 CLI" 1>&2 && \
      wget --quiet \
        --output-document "/dev/stdout" \
        "https://stratus-documentation-us-east-1-public.s3.amazonaws.com/cli/${ICAV2_CLI_VERSION}/ica-linux-${TARGETPLATFORM#linux/}.zip" | \
      busybox unzip -p - "linux-${TARGETPLATFORM#linux/}/icav2" > "/usr/local/bin/icav2" && \
      chmod +x "/usr/local/bin/icav2" \
    ) && \
    ( \
      echo "Adding user groups" 1>&2 && \
      addgroup \
        --gid "${GITHUB_ACTIONS_GROUP_ID}" \
        "${GITHUB_ACTIONS_GROUP_NAME}" && \
      adduser \
        --disabled-password \
        --gid "${GITHUB_ACTIONS_GROUP_ID}" \
        --uid "${GITHUB_ACTIONS_USER_ID}" \
        "${GITHUB_ACTIONS_USER_NAME}" \
    )


# Copy over source to . for user to install
COPY . "/cwl-ica-src-temp/"

RUN ( \
      rsync \
        --archive --remove-source-files \
        --chown "${GITHUB_ACTIONS_USER_ID}:${GITHUB_ACTIONS_GROUP_ID}" "/cwl-ica-src-temp/" "/home/${GITHUB_ACTIONS_USER_NAME}/cwl-ica-src/" \
    )

# Switch to conda user
USER "${GITHUB_ACTIONS_USER_NAME}"
ENV USER="${GITHUB_ACTIONS_USER_NAME}"
ENV PATH="${CONDA_DIR}/bin:${PATH}"

# Add conda command
RUN ( \
      echo "Adding in package and env paths to conda arc" 1>&2 && \
      conda config --append pkgs_dirs "\$HOME/.conda/pkgs" && \
      conda config --append envs_dirs "\$HOME/.conda/envs" && \
      echo "Installing into a conda env" 1>&2 && \
      ( \
        cd "/home/${GITHUB_ACTIONS_USER_NAME}" && \
        bash "cwl-ica-src/install.sh" -y -s && \
        rm -rf "cwl-ica-src/" \
      ) \
    )

# Set environment variables for user
ENV CONDA_PREFIX="/home/${GITHUB_ACTIONS_USER_NAME}/.conda/envs/${CONDA_ENV_NAME}"
ENV CONDA_DEFAULT_ENV="${CONDA_ENV_NAME}"

RUN ( \
      cd "/home/${GITHUB_ACTIONS_USER_NAME}" && \
      echo "Creating ${ICAV2_PLUGINS_CLI_CONDA_ENV_NAME} environment for icav2 cli plugins" 1>&2 && \
      conda create --yes \
        --name "${ICAV2_PLUGINS_CLI_CONDA_ENV_NAME}" \
        python="${ICAV2_PLUGINS_CLI_CONDA_PYTHON_VERSION}" && \
      echo "Installing ICAv2 CLI Plugins" 1>&2 && \
      wget --quiet \
        --output-document "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" \
        "https://github.com/umccr/icav2-cli-plugins/releases/download/${ICAV2_PLUGINS_CLI_VERSION}/icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" && \
      unzip -qq "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" && \
      PATH="/home/${GITHUB_ACTIONS_USER_NAME}/.conda/envs/${ICAV2_PLUGINS_CLI_CONDA_ENV_NAME}/bin:${PATH}" \
      bash "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}/install.sh" "--no-autocompletion" && \
      rm -rf "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}" "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" \
    )

# Add conda env to path
ENV PATH="/home/${GITHUB_ACTIONS_USER_NAME}/.conda/envs/${CONDA_ENV_NAME}/bin:${PATH}"
# Set ICAv2 CLI plugins home
ENV ICAV2_CLI_PLUGINS_HOME="/home/${GITHUB_ACTIONS_USER_NAME}/.icav2-cli-plugins/"

# Add cwl-utils (with cwl-inputs-schema-gen) to cwl-ica environment
RUN ( \
      cd "/home/${GITHUB_ACTIONS_USER_NAME}" && \
      echo "Cloning cwl-utils" 1>&2 && \
      git clone --branch "${CWL_UTILS_REPO_BRANCH}" "${CWL_UTILS_REPO_PATH}" "cwl-utils" && \
      echo "Installing cwl-utils" 1>&2 && \
      ( \
        cd 'cwl-utils' && \
        "/home/${GITHUB_ACTIONS_USER_NAME}/.conda/envs/${CONDA_ENV_NAME}/bin/pip" install . \
      ) && \
      echo "Cleaning up" 1>&2 && \
      rm -rf cwl-utils \
    )

# Set entrypoint
CMD "cwl-ica"
