FROM docker.io/condaforge/mambaforge:24.1.2-0

# Set args
ARG CONDA_GROUP_NAME="cwl_ica_group"
ARG CONDA_GROUP_ID=1000
ARG CONDA_USER_NAME="cwl_ica_user"
ARG CONDA_USER_ID=1000
ARG CONDA_ENV_NAME="cwl-ica"
ARG YQ_VERSION="v4.35.2"
ARG ICAV2_PLUGINS_CLI_VERSION="v2.20.1"
ARG ICAV2_PLUGINS_CLI_CONDA_PYTHON_VERSION="3.11"
ARG ICAV2_PLUGINS_CLI_CONDA_ENV_NAME="python3.11"
ARG CURL_VERSION="7.81.0"
ARG CWL_UTILS_REPO_PATH="https://github.com/alexiswl/cwl-utils"
ARG CWL_UTILS_REPO_BRANCH="enhancement/cwl-inputs-schema-gen"

RUN export DEBIAN_FRONTEND=noninteractive && \
    echo "Updating Apt" 1>&2 && \
    apt-get update -y -q && \
    echo "Installing jq, nodejs, rsync, graphviz and parallel" 1>&2 && \
    apt-get install -y -q \
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
      autoconf && \
    echo "Cleaning up after apt installations" 1>&2 && \
    apt-get clean -y && \
    echo "Installing yq" 1>&2 && \
    wget --quiet \
      --output-document /usr/bin/yq \
      "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64" && \
    chmod +x /usr/bin/yq && \
    echo "Installing gh binary" && \
    curl --fail --silent --show-error --location \
      "https://cli.github.com/packages/githubcli-archive-keyring.gpg" | \
    dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | \
    tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \
    apt-get update -y -q && \
    apt install gh -y -q && \
    echo "Installing aws cli" 1>&2 && \
    wget --quiet "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" \
      --output-document "awscliv2.zip" && \
    unzip -qq awscliv2.zip && \
    ./aws/install && \
    rm -rf aws/ awscliv2.zip && \
    echo "Removing existing installation of curl" && \
    apt-get purge -y -q --auto-remove curl && \
    echo "Installing curl (that supports --fail-with-body parameter)" 1>&2 && \
    ( \
      wget "https://curl.haxx.se/download/curl-${CURL_VERSION}.tar.gz" && \
      tar -xzf "curl-${CURL_VERSION}.tar.gz" && \
      cd "curl-${CURL_VERSION}" && \
      autoreconf -fi && \
      ./configure \
        --prefix=/usr \
        --with-ssl \
        --with-nghttp2 && \
      make -j4 && \
      make install && \
      ldconfig \
    ) && \
    rm -rf curl-${CURL_VERSION}/ curl-${CURL_VERSION}.tar.gz && \
    echo "Updating conda" 1>&2 && \
    conda update --yes \
      --name base \
      --channel conda-forge \
      --channel defaults \
      conda && \
    echo "Updating mamba" 1>&2 && \
    mamba update --yes \
      --quiet \
      --name base \
      --channel conda-forge \
      --channel defaults \
      mamba && \
    echo "Cleaning conda" 1>&2 && \
    conda clean --all --yes --quiet && \
    echo "Cleaning mamba "1>&2 && \
    mamba clean --all --yes --quiet && \
    echo "Adding user groups" 1>&2 && \
    addgroup \
      --gid "${CONDA_GROUP_ID}" \
      "${CONDA_GROUP_NAME}" && \
    adduser \
      --disabled-password \
      --gid "${CONDA_GROUP_ID}" \
      --uid "${CONDA_USER_ID}" "${CONDA_USER_NAME}"


# Copy over source to . for user
COPY . "/cwl-ica-src-temp/"

RUN \
    cp -r "/cwl-ica-src-temp/." "/home/${CONDA_USER_NAME}/cwl-ica-src/" && \
    chown -R "${CONDA_USER_ID}:${CONDA_GROUP_ID}" "/home/${CONDA_USER_NAME}/cwl-ica-src/" && \
    rm -rf  "/cwl-ica-src-temp/"

# Switch to conda user
USER "${CONDA_USER_NAME}"
ENV USER="${CONDA_USER_NAME}"

# Add conda command
RUN echo "Adding in package and env paths to conda arc" 1>&2 && \
    conda config --append pkgs_dirs "\$HOME/.conda/pkgs" && \
    conda config --append envs_dirs "\$HOME/.conda/envs" && \
    echo "Installing into a conda env" 1>&2 && \
    ( \
      cd "/home/${CONDA_USER_NAME}" && \
      bash "cwl-ica-src/install.sh" -y -s && \
      rm -rf "cwl-ica-src/" \
    )

# Set environment variables for user
ENV CONDA_PREFIX="/home/${CONDA_USER_NAME}/.conda/envs/${CONDA_ENV_NAME}"
ENV CONDA_DEFAULT_ENV="${CONDA_ENV_NAME}"

RUN ( \
      cd "/home/${CONDA_USER_NAME}" && \
      echo "Creating ${ICAV2_PLUGINS_CLI_CONDA_ENV_NAME} environment for icav2 cli plugins" 1>&2 && \
      mamba create --yes \
        --name "${ICAV2_PLUGINS_CLI_CONDA_ENV_NAME}" \
        python="${ICAV2_PLUGINS_CLI_CONDA_PYTHON_VERSION}" && \
      echo "Installing ICAv2 CLI Plugins" 1>&2 && \
      wget --quiet \
        --output-document "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" \
        "https://github.com/umccr/icav2-cli-plugins/releases/download/${ICAV2_PLUGINS_CLI_VERSION}/icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" && \
      unzip -qq "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" && \
      PATH="/home/${CONDA_USER_NAME}/.conda/envs/${ICAV2_PLUGINS_CLI_CONDA_ENV_NAME}/bin:${PATH}" \
      bash "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}/install.sh" "--no-autocompletion" && \
      rm -rf "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}" "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" \
    )

ENV PATH="/home/${CONDA_USER_NAME}/.conda/envs/${CONDA_ENV_NAME}/bin:${PATH}"
ENV ICAV2_CLI_PLUGINS_HOME="/home/${CONDA_USER_NAME}/.icav2-cli-plugins/"

# Add cwl-utils (with cwl-inputs-schema-gen) to cwl-ica environment
RUN ( \
      cd "/home/${CONDA_USER_NAME}" && \
      echo "Cloning cwl-utils" 1>&2 && \
      git clone --branch "${CWL_UTILS_REPO_BRANCH}" "${CWL_UTILS_REPO_PATH}" "cwl-utils" && \
      echo "Installing cwl-utils" 1>&2 && \
      ( \
        cd 'cwl-utils' && \
        "/home/${CONDA_USER_NAME}/.conda/envs/${CONDA_ENV_NAME}/bin/pip" install . \
      ) && \
      echo "Cleaning up" 1>&2 && \
      rm -rf cwl-utils \
    )


CMD "cwl-ica"
