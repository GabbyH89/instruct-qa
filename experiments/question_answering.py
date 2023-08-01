import argparse
import logging
import os

from rag_eval.prompt.templates import HistoryTemplate, PromptTemplate, PassageTemplate, StarChatTemplate
from rag_eval.retrieval import RetrieverFromFile
from rag_eval.retrieval.utils import load_retriever, load_index
from rag_eval.response_runner import ResponseRunner, ConvQAResponseRunner, StarChatResponseRunner, FaithDialResponseRunner
from rag_eval.collections.utils import load_collection
from rag_eval.generation.utils import load_model
from rag_eval.dataset.utils import load_dataset
from rag_eval.experiment_utils import log_commandline_args, generate_experiment_id

thisdir = os.path.dirname(os.path.realpath(__file__))
parser = argparse.ArgumentParser(description="Evaluates a model against a QA dataset.")
parser.add_argument(
    "--persistent_dir",
    action="store",
    type=str,
    default=os.path.realpath(os.path.join(thisdir, "..")),
)
parser.add_argument(
    "--model_name",
    action="store",
    type=str,
    default="opt-125m",
    help="The model to evaluate.",
)
parser.add_argument(
    "--weights_path",
    action="store",
    type=str,
    default=None,
    help="The path to the directory for local weights of the models e.g., llama, alpaca, etc.",
)
parser.add_argument(
    "--dataset_name",
    action="store",
    type=str,
    default="hotpot_qa",
    help="The dataset to evaluate against.",
)
parser.add_argument(
    "--dataset_type",
    action="store",
    type=str,
    default="qa",
    choices=["qa", "conv_qa", "qa_unanswerable", "conv_qa_unanswerable", "starcoder_chat", "faithdial"],
    help="The type of dataset to evaluate against.",
)
parser.add_argument(
    "--dataset_config_name",
    action="store",
    type=str,
    default=None,
    help="The specific dataset configuration to use.",
)
parser.add_argument(
    "--dataset_split",
    action="store",
    type=str,
    default="validation",
    help="The split of the dataset to use.",
)
parser.add_argument(
    "--dataset_file_path",
    action="store",
    type=str,
    default=None,
    help="The path to the dataset file.",
)
parser.add_argument(
    "--temperature",
    action="store",
    type=float,
    default=1.0,
    help="The temperature to use during generation.",
)
parser.add_argument(
    "--top_p",
    action="store",
    type=float,
    default=0.95,
    help="The Nucleus Sampling parameter to use during generation.",
)
parser.add_argument(
    "--min_new_tokens",
    action="store",
    type=int,
    default=20,
    help="The minimum number of tokens to generate.",
)
parser.add_argument(
    "--max_new_tokens",
    action="store",
    type=int,
    default=64,
    help="The maximum number of tokens to generate.",
)
parser.add_argument(
    "--api_key",
    action="store",
    type=str,
    default=None,
    help="API key if generating from OpenAI model.",
)
parser.add_argument(
    "--document_collection_name",
    action="store",
    type=str,
    default="dpr_wiki_collection",
    help="Document collection to retrieve from.",
)
parser.add_argument(
    "--document_cache_dir",
    action="store",
    type=str,
    default=None,
    help="Directory that document collection is cached in.",
)
parser.add_argument(
    "--document_file_name",
    action="store",
    type=str,
    default=None,
    help="Basename of the path to the file containing the document collection.",
)
parser.add_argument(
    "--batch_size",
    action="store",
    type=int,
    default=1,
    help="Batch size to use for generation.",
)
parser.add_argument(
    "--logging_interval",
    action="store",
    type=int,
    default=256,
    help="Step frequency to write results to disk.",
)
parser.add_argument(
    "--k",
    action="store",
    type=int,
    default=10,
    help="Number of passages to retrieve.",
)
parser.add_argument(
    "--retriever_name",
    action="store",
    type=str,
    default="all-MiniLM-L6-v2",
    help="Name of the retriever to load.",
)
parser.add_argument(
    "--index_name",
    action="store",
    type=str,
    default=None,
    help="Name of the index to use for retrieval.",
)
parser.add_argument(
    "--index_path",
    action="store",
    type=str,
    default=None,
    help="Path to the index to use for retrieval.",
)
parser.add_argument(
    "--seed",
    action="store",
    type=int,
    default=0,
    help="Seed for RNG.",
)

parser.add_argument(
    "--use_hosted_retriever",
    choices=["true", "false"],
    default="true",
    help="Whether to use the hosted retriever.",
)

parser.add_argument(
    "--hosted_retriever_url",
    action="store",
    type=str,
    default="http://10.140.16.91:42010/search",
    help="URL of the hosted retriever, if use_hosted_retriever is true.",
)

parser.add_argument(
    "--retriever_cached_results_fp",
    action="store",
    type=str,
    default=None,
    help="Path to the file containing cached retriever results.",
)

if __name__ == "__main__":
    args = parser.parse_args()

    # Create a logger that logs to the console.
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(os.path.basename(__file__))

    logger.info("Evaluating model:")
    log_commandline_args(args, logger.info)

    experiment_id = generate_experiment_id(
        name=args.dataset_name,
        split=args.dataset_split,
        collection_name=args.document_collection_name,
        model_name=args.model_name.replace("/", "_"),
        retriever_name=args.retriever_name,
        top_p=args.top_p,
        temperature=args.temperature,
        seed=args.seed,
    )

    logger.info(f"Experiment ID: {experiment_id}")
    dataset = load_dataset(
        args.dataset_name,
        split=args.dataset_split,
        name=args.dataset_config_name,
        file_path=args.dataset_file_path,
    )
    output_file = f"{args.persistent_dir}/results/{args.dataset_name}/response/{experiment_id}.jsonl"
    logger.info(f"Output response file: {output_file}")
    logger.info(f"Length of dataset: {len(dataset)}")

    logger.info("Loading document collection...")
    document_collection = load_collection(
        args.document_collection_name,
        cache_dir=args.document_cache_dir,
        file_name=args.document_file_name,
    )

    logger.info("Loading generation model...")
    model = load_model(
        args.model_name,
        weights_path=args.weights_path,
        temperature=args.temperature,
        top_p=args.top_p,
        min_new_tokens=args.min_new_tokens,
        max_new_tokens=args.max_new_tokens,
        api_key=args.api_key,
    )

    index = None
    if args.index_name is not None:
        logger.info("Loading index...")
        index = load_index(args.index_name, args.index_path)

    retriever = None
    if index is not None or args.retriever_cached_results_fp is not None:
        logger.info("Loading retriever...")
        retriever = load_retriever(
            args.retriever_name,
            index,
            retriever_cached_results_fp=args.retriever_cached_results_fp,
        )

    # TODO: Move this elsewhere. We'll want a common location for general prompts.
    history_template = None
    prompt_template = None
    if args.dataset_type == "qa":
        template = "Please answer the following question given the following passages:\n{retrieved_passages}\nQuestion: {query}\nAnswer: "

        prompt_template = PromptTemplate(
            variables=["query", "retrieved_passages"],
            template=template,
        )
    elif args.dataset_type == "qa_unanswerable":
        template = "Please answer the following question given the following passage. If the answer is not in the passage or cannot be inferred from the passage, respond as \"I don't know\".\n{retrieved_passages}\nQuestion: {query}\nAnswer: "
        prompt_template = PromptTemplate(
            variables=["query", "retrieved_passages"],
            template=template,
        )

    elif args.dataset_type == "conv_qa":
        template = "Please answer the following question given the following passages and the conversation history:\n\n{retrieved_passages}\n\n{history}\nUser: {query}\nAgent: "

        prompt_template = PromptTemplate(
            variables=["query", "retrieved_passages", "history"],
            template=template,
        )

        history_template = HistoryTemplate()
    
    elif args.dataset_type == "conv_qa_unanswerable":
        template = "Please answer the following question given the following passage and the conversation history. If the answer is not in the passage or cannot be infered from the passage, respond as \"I don't know\".\n\n{retrieved_passages}\n\n{history}\nUser: {query}\nAgent: "

        prompt_template = PromptTemplate(
            variables=["query", "retrieved_passages", "history"],
            template=template,
        )

        history_template = HistoryTemplate()

    elif args.dataset_type == "starcoder_chat":
        prompt_template = StarChatTemplate()
    
    elif args.dataset_type == "faithdial":
        history_template = HistoryTemplate()
    
    else:
        assert False, f"Unknown dataset type: {args.dataset_type}"

    passage_str = "- Title: {title}\n{text}\n\n"

    passage_template = PassageTemplate(
        variables=["title", "text"], template=passage_str
    )

    os.makedirs(
        f"{args.persistent_dir}/results/{args.dataset_name}/response", exist_ok=True
    )

    if args.dataset_type in ["qa", "qa_unanswerable"]:
        runner_cls = ResponseRunner
    elif args.dataset_type in ["conv_qa", "conv_qa_unanswerable"]:
        runner_cls = ConvQAResponseRunner
    elif args.dataset_type == "starcoder_chat":
        runner_cls = StarChatResponseRunner
    elif args.dataset_type == "faithdial":
        runner_cls = FaithDialResponseRunner
    else:
        assert False, f"Unknown dataset type: {args.dataset_type}"

    runner = runner_cls(
        model=model,
        dataset=dataset,
        retriever=retriever,
        document_collection=document_collection,
        prompt_template=prompt_template,
        passage_template=passage_template,
        history_template=history_template,
        output_path=output_file,
        batch_size=args.batch_size,
        logging_interval=args.logging_interval,
        use_hosted_retriever=args.use_hosted_retriever == "true",
        hosted_retriever_url=args.hosted_retriever_url,
        use_cached_retrieved_results=isinstance(retriever, RetrieverFromFile),
    )
    runner()