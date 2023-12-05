# Note: We will not use the HF transformers pipeline directly,
# but will instead use the library 'bert-extractive-summarizer',
# which implements the architecture in this paper:
# https://arxiv.org/ftp/arxiv/papers/1906/1906.04165.pdf.

# This library makes use of the sentence embeddings outputted by BERT,
# and then uses a clustering algorithm to find the most representative
# sentences in the text. This is a more robust approach than the
# transformer pipeline, and will be better than specifying a specific
# range of tokens / ratio of summarization to return.

# Transformers pipeline from HF will automatically detect
# and use CUDA GPU if available

from transformers import pipeline

bert_summarizer = pipeline(
    "summarization",
    model="facebook/bart-large-cnn",
    tokenizer="facebook/bart-large-cnn",
)
MIN_LENGTH = 0.1
MAX_LENGTH = 0.25

# The `bert-extractive-summarizer` library will use CUDA
# GPU if available by default, and requires pytorch.

from summarizer import Summarizer  # Bert Summarizer

model = Summarizer()

K_MAX = 4  # Max num of sentences in our cluster, to return in summary


class Summarizer:
    """
    Summarizes text using Bert Summarizer with sentence embeddings.

    In the future, we should have multiple summarizers to choose from,
    such as LexRank, TextRank, etc. and we should have a way to dynamically
    choose the best summarizer for the given text based on the length.

    Since BERT has an input length limit of 512 tokens, it will not be the
    best choice for large contexts or lengthy articles.
    """

    def __init__(self) -> None:
        return

    def clean_text(self, text: str) -> str:
        """
        Cleans text by removing newlines and extra spaces.

        Args:
            text (str): Text to clean

        Returns:
            str: Cleaned text
        """
        # Remove newlines
        text = text.replace("\n", " ")
        # Remove extra spaces
        text = " ".join(text.split())
        return text

    def summarize(
        self, text: str, min_length: float = MIN_LENGTH, max_length: float = MAX_LENGTH
    ) -> str:
        """
        Summarizes text with BERT model using HF transformers pipeline.

        Args:
            text (str): _description_
            min_length (float, optional): _description_. Defaults to MIN_LENGTH.
            max_length (float, optional): _description_. Defaults to MAX_LENGTH.

        Returns:
            str: _description_
        """
        # Limit text to 512 tokens since that's Bert's max input length
        text = " ".join(text.split(" ")[:512])
        # print("The text to summarize: ", text)
        min_length = round(min_length * len(text.split(" ")))
        # print("Min length found: ", min_length)
        max_length = round(max_length * len(text.split(" ")))
        # print("Max length found: ", max_length)
        result = bert_summarizer(
            text, min_length=min_length, max_length=max_length, do_sample=False
        )[0]["summary_text"]
        return result

    def summarize_optimal(self, text: str, max_sentences: int = K_MAX) -> str:
        """
        Summarizes text using Bert Summarizer with sentence embeddings
        and clustering to find the most relevant sentences.

        Args:
            text (str): Text to summarize
            max_sentences (int, optional): Max number of sentences to return in summary.
                Defaults to K_MAX.

        Returns:
            str: Summarized text
        """
        text = self.clean_text(text)
        num_sentences = model.calculate_optimal_k(text, k_max=max_sentences)
        return model(text, num_sentences=num_sentences)


if __name__ == "__main__":
    summarizer = Summarizer()
    example_text = """Biden opposes changing Senate rules to raise debt limitPOLITICO2 hours 
                    agobookmark_bordersharemore_vertJoe: GOP Spent Like 'Drunken Socialists.' Now
                    They Refuse To Pay For It.MSNBC10 hours agobookmark_bordersharemore_vertMcConnell
                    blocks Schumer bid to raise debt ceiling by majority voteFox Business2 hours 
                    agobookmark_bordersharemore_vertOpinion | Mitch McConnell's ugly tactics should prompt
                    Democrats to nullify the debt limitThe Washington Post8 hours 
                    agoOpinionbookmark_bordersharemore_vertOpinion | The Republican Senate Spending Bill Vote
                    Was SabotageThe New York Times7 hours agoOpinionbookmark_bordersharemore_vertView Full
                    Coveragekeyboard_arrow_up"""
    print("Summarizing example text: " + example_text)
    summarized = summarizer.summarize(example_text)
    print(summarized)
else:
    summarizer = Summarizer()
