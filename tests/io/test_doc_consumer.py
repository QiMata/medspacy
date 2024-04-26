import os, sys
# recent pytest failed because of project directory is not included in sys.path somehow, might due to other configuration issue. Add this for a temp solution
sys.path.append(os.getcwd())
import spacy
from spacy.pipeline import EntityRuler

from medspacy.io import DocConsumer
from medspacy.io.doc_consumer import (
    DEFAULT_ENT_ATTRS,
    DEFAULT_DOC_ATTRS,
    ALLOWED_CONTEXT_ATTRS,
    ALLOWED_SECTION_ATTRS,
    ALLOWED_DATA_TYPES,
)
from medspacy.context import ConText
from medspacy.section_detection import Sectionizer, SectionRule

nlp = spacy.load("en_core_web_sm")
nlp.remove_pipe("ner")

matcher = nlp.add_pipe("entity_ruler")
matcher.add_patterns([{"label": "PROBLEM", "pattern": "cough"}])

nlp.add_pipe("medspacy_context")

sectionizer = nlp.add_pipe("medspacy_sectionizer")
sectionizer.add(
    [
        SectionRule("Section 1:", "section1"),
        SectionRule("Section 2:", "section2", parents=["section1"]),
    ]
)

simple_text = "Patient has a cough."
context_text = "Patient has no cough."
section_text = "Section 1: Patient has a cough"
section_parent_text = """Section 1: comment
Section 2: Patient has a cough"""
many_concept_texts = ["cough " * i for i in range(10)]

simple_doc = nlp(simple_text)
context_doc = nlp(context_text)
section_doc = nlp(section_text)
section_parent_doc = nlp(section_parent_text)
many_concept_docs = [nlp(t) for t in many_concept_texts]


class TestDocConsumer:
    def test_init_default(self):
        doc_consumer = DocConsumer(nlp)
        assert DocConsumer(nlp)
        assert doc_consumer.dtypes == ("ents",)

    def test_init_context(self):
        doc_consumer = DocConsumer(nlp, dtypes=("context",))
        assert doc_consumer.dtypes == ("context",)

    def test_default_cols(self):
        consumer = DocConsumer(nlp)
        doc = consumer(simple_doc)
        data = doc._.get_data("ents")
        assert data is not None
        assert set(data.keys()) == set(consumer.dtype_attrs["ents"])
        assert set(data.keys()) == set(DEFAULT_ENT_ATTRS)

    def test_context_cols(self):
        consumer = DocConsumer(nlp, dtypes=("context",))
        doc = consumer(context_doc)
        data = doc._.get_data("context")
        assert data is not None
        assert set(data.keys()) == set(ALLOWED_CONTEXT_ATTRS)

    def test_section_cols(self):
        consumer = DocConsumer(nlp, dtypes=("section",))
        doc = consumer(context_doc)
        data = doc._.get_data("section")
        assert data is not None
        assert set(data.keys()) == set(ALLOWED_SECTION_ATTRS)

    def test_all_dtypes(self):
        consumer = DocConsumer(nlp, dtypes="all")
        assert consumer.dtypes == ALLOWED_DATA_TYPES

    def test_default_data(self):
        consumer = DocConsumer(nlp)
        doc = consumer(simple_doc)
        data = doc._.get_data("ents")
        ent = doc.ents[0]
        assert data["text"][0] == ent.text
        assert data["label_"][0] == ent.label_
        assert data["start_char"][0] == ent.start_char
        assert data["end_char"][0] == ent.end_char

    def test_context_data(self):
        consumer = DocConsumer(nlp)
        doc = consumer(context_doc)
        data = doc._.get_data("ents")
        ent = doc.ents[0]
        assert data["is_family"][0] == ent._.is_family
        assert data["is_hypothetical"][0] == ent._.is_hypothetical
        assert data["is_historical"][0] == ent._.is_historical
        assert data["is_uncertain"][0] == ent._.is_uncertain
        assert data["is_negated"][0] == ent._.is_negated

    def test_section_data_ent(self):
        consumer = DocConsumer(nlp)
        doc = consumer(section_doc)
        data = doc._.get_data("ents")
        ent = doc.ents[0]
        assert data["section_category"][0] == ent._.section_category
        assert data["section_parent"][0] == ent._.section_parent

    def test_section_data_ent_parent(self):
        consumer = DocConsumer(nlp)
        doc = consumer(section_parent_doc)
        data = doc._.get_data("ents")
        ent = doc.ents[0]
        assert data["section_category"][0] == ent._.section_category
        assert data["section_parent"][0] == ent._.section_parent

    def test_section_data_section(self):
        consumer = DocConsumer(nlp, dtypes=("section",))
        doc = consumer(section_doc)
        data = doc._.get_data("section")
        section = doc._.sections[0]
        section_title = doc[section.title_span[0] : section.title_span[1]]
        section_body = doc[section.body_span[0] : section.body_span[1]]
        assert data["section_category"][0] == section.category
        assert data["section_title_text"][0] == section_title.text
        assert data["section_title_start_char"][0] == section_title.start_char
        assert data["section_title_end_char"][0] == section_title.end_char
        assert data["section_body"][0] == section_body.text
        assert data["section_body_start_char"][0] == section_body.start_char
        assert data["section_body_end_char"][0] == section_body.end_char
        assert data["section_parent"][0] == section.parent

    def test_ten_concepts(self):
        consumer = DocConsumer(nlp, dtypes=("ents",))
        docs = [consumer(d) for d in many_concept_docs]
        for doc in docs:
            print(doc)
            num_concepts = len(doc.ents)
            data = doc._.get_data("ents")
            for key in data.keys():
                print(key)
                print(num_concepts)
                print(data[key])
                assert num_concepts == len(data[key])

    def test_get_default_attrs(self):
        attrs = DocConsumer.get_default_attrs()
        assert set(attrs.keys()) == {"ents", "group", "context", "section", "doc"}
        assert set(attrs["ents"]) == set(DEFAULT_ENT_ATTRS)
        assert set(attrs["group"]) == set(DEFAULT_ENT_ATTRS)
        assert set(attrs["section"]) == set(ALLOWED_SECTION_ATTRS)
        assert set(attrs["context"]) == set(ALLOWED_CONTEXT_ATTRS)
        assert set(attrs["doc"]) == set(DEFAULT_DOC_ATTRS)

    def test_get_data_attrs_not_none(self):
        consumer = DocConsumer(nlp)
        doc = consumer(simple_doc)
        data = doc._.get_data("ents", attrs=["label_", "is_negated"])
        assert set(data.keys()) == {"label_", "is_negated"}

    def test_context_data_custom_ent_attribute(self):
        """Test that we can add a custom Span._ attribute to the ConText data output."""
        consumer = DocConsumer(nlp, dtypes=("context",),
                               dtype_attrs={"context": ("modifier_text", "modifier_category", "my_custom_attr")})
        from spacy.tokens import Span; Span.set_extension("my_custom_attr", force=True, default="")
        doc = nlp(context_text)
        assert len(doc._.context_graph.edges) == 1
        doc.ents[0]._.my_custom_attr = "Hello!"
        consumer(doc)
        doc_data = doc._.data
        assert isinstance(doc_data, dict)
        assert doc_data.keys() == {"context"}
        assert set(doc_data["context"].keys()) == {"modifier_text", "modifier_category", "my_custom_attr"}
        assert doc_data["context"]["my_custom_attr"][0] == "Hello!"